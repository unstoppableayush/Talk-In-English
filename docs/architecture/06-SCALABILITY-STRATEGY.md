# Scalability Strategy

## Scaling Dimensions

```
                    ┌──────────────────────────────────────┐
                    │         SCALING TARGETS               │
                    │                                        │
                    │  Concurrent users:     10K → 100K+    │
                    │  Concurrent sessions:  1K → 10K+      │
                    │  Messages/sec:         5K → 50K+      │
                    │  WebSocket conns:      10K → 100K+    │
                    │  Public room listeners: Unlimited      │
                    └──────────────────────────────────────┘
```

---

## 1. Horizontal Service Scaling

### Stateless Services (scale freely)
All services are designed stateless — session state lives in Redis, persistent state in PostgreSQL.

```
                    NGINX Load Balancer
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         api-gw-1     api-gw-2     api-gw-3
              │            │            │
              ▼            ▼            ▼
         session-1    session-2    session-3
              │            │            │
              └────────────┼────────────┘
                           │
                     Redis Cluster
```

**Auto-scaling rules (Kubernetes HPA):**

| Service | Scale Metric | Target | Min | Max |
|---------|-------------|--------|-----|-----|
| api-gateway | CPU 70% / RPS | 1000 req/s per pod | 2 | 10 |
| session-service | WebSocket connections | 5000 conns per pod | 2 | 20 |
| ai-service | Queue depth | 100 pending per pod | 2 | 15 |
| eval-service | CPU 70% | — | 1 | 5 |
| media-service | CPU 80% / audio streams | 500 streams per pod | 2 | 10 |
| worker-service | Celery queue depth | 50 tasks per worker | 2 | 10 |

---

## 2. WebSocket Scaling

### The Challenge
WebSocket connections are persistent and stateful — a user connected to `session-1` pod needs messages from users on `session-2` pod.

### Solution: Redis Pub/Sub as Message Bus

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ session-pod-1│      │ session-pod-2│      │ session-pod-3│
│              │      │              │      │              │
│ User A (ws)  │      │ User B (ws)  │      │ Listener (ws)│
│ User C (ws)  │      │ User D (ws)  │      │ Listener (ws)│
└──────┬───────┘      └──────┬───────┘      └──────┬───────┘
       │                     │                     │
       └─────────────────────┼─────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Redis Pub/Sub  │
                    │                 │
                    │  Channel:       │
                    │  session.{id}   │
                    └─────────────────┘

Flow:
1. User A sends message → session-pod-1 receives
2. session-pod-1 publishes to Redis channel "session.{id}"
3. session-pod-2 and session-pod-3 are subscribed → receive
4. Each pod broadcasts to its locally-connected users
```

### Connection Routing (Sticky Sessions)
- NGINX uses IP-hash or cookie-based sticky sessions for WebSocket upgrades
- On reconnect, client may land on different pod → Redis Pub/Sub ensures state sync
- Each pod maintains a local connection registry: `{session_id → [WebSocket]}`

### Connection Limits Per Pod
- Target: 5,000 WebSocket connections per pod
- Monitor with: file descriptor count, memory usage, event loop lag
- Scale out when approaching 80% of limit

---

## 3. Listener Scaling (Unlimited Listeners)

The critical scalability challenge: a popular room could have thousands of listeners.

### Tiered Broadcast Architecture

```
                        ┌──────────────┐
                        │  Origin Pod  │  (where speakers are connected)
                        │  Session Svc │
                        └──────┬───────┘
                               │
                    Message published to Redis
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       ┌──────────┐    ┌──────────┐    ┌──────────┐
       │ Relay-1  │    │ Relay-2  │    │ Relay-3  │    (Fan-out relay pods)
       │ 5K conns │    │ 5K conns │    │ 5K conns │
       └──────────┘    └──────────┘    └──────────┘
           │               │               │
        ┌──┴──┐         ┌──┴──┐         ┌──┴──┐
       Listeners       Listeners       Listeners
```

**Relay pods:**
- Lightweight WebSocket servers that only broadcast (no business logic)
- Subscribe to Redis channels for their assigned sessions
- Each handles 5K–10K listener connections
- Auto-scale based on connection count

**For extreme scale (>50K listeners):**
- Add CDN-based HLS/DASH streaming for audio
- Convert real-time audio to a stream that CDN edges can cache

---

## 4. Database Scaling

### PostgreSQL Strategy

**Phase 1 (0 → 10K users):**
- Single PostgreSQL instance with read replicas
- Connection pooling via PgBouncer (pool_mode=transaction)
- Max connections: 200 (PgBouncer → 20 actual PG connections)

```
App Pods ──► PgBouncer ──► PostgreSQL Primary
                               │
                          ┌────┴────┐
                          ▼         ▼
                      Replica-1  Replica-2  (read-only queries)
```

**Phase 2 (10K → 100K users):**
- Table partitioning for `messages` (by month)
- Separate read replicas for analytics vs. operational queries
- Consider Citus for horizontal sharding if needed

**Phase 3 (100K+ users):**
- Shard `messages` table by session_id hash
- Separate databases per service (auth DB, sessions DB, eval DB)
- Archive old sessions to cold storage (S3 + Athena for querying)

**Partitioning Strategy for Messages:**
```sql
-- Partition messages by month
CREATE TABLE sessions.messages (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ...
) PARTITION BY RANGE (created_at);

CREATE TABLE sessions.messages_2026_03
    PARTITION OF sessions.messages
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

-- Auto-create partitions via pg_partman
```

---

## 5. Redis Scaling

### Architecture
```
┌─────────────────────────────────────────┐
│            Redis Cluster (6 nodes)       │
│                                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │Master 1 │  │Master 2 │  │Master 3 │ │
│  │ Slots   │  │ Slots   │  │ Slots   │ │
│  │ 0-5460  │  │5461-10922│ │10923-   │ │
│  └────┬────┘  └────┬────┘  │  16383  │ │
│       │            │       └────┬────┘ │
│  ┌────▼────┐  ┌────▼────┐  ┌────▼────┐ │
│  │Replica 1│  │Replica 2│  │Replica 3│ │
│  └─────────┘  └─────────┘  └─────────┘ │
└─────────────────────────────────────────┘
```

**Usage breakdown:**
| Use Case | Data Structure | TTL |
|----------|---------------|-----|
| Active session state | Hash | Session duration + 1h |
| Connection registry | Set | Connection duration |
| Pub/Sub channels | Pub/Sub | N/A (real-time) |
| Rate limiting | Sorted Set / String | Window duration |
| JWT blocklist | Set | Token expiry |
| Session cache | String (JSON) | 5 min |
| Celery task queue | List / Stream | Until consumed |

**Memory estimate:**
- Per active session: ~5 KB (state + participants)
- Per WebSocket connection tracking: ~200 bytes
- At 10K concurrent sessions: ~50 MB
- Redis cluster: 3 nodes × 2 GB = comfortable headroom

---

## 6. AI / LLM Scaling

### Challenge
LLM API calls are expensive (cost + latency). Must optimize throughput and manage costs.

### Strategies

**Request Queuing:**
```
┌──────────┐    ┌──────────────┐    ┌──────────┐
│ Session   │───►│ Request Queue │───►│ AI Worker│──► LLM API
│ Service   │    │ (Redis)       │    │ Pool     │
└──────────┘    └──────────────┘    └──────────┘
                                     │ AI Worker│──► LLM API
                                     │ AI Worker│──► LLM API
                                     └──────────┘
```

**Cost Optimization:**
| Strategy | Savings | Implementation |
|----------|---------|----------------|
| Prompt caching | 30-50% | Cache system prompts + common patterns |
| Model tiering | 40-60% | GPT-4o for evaluation, GPT-4o-mini for moderation |
| Batch evaluation | 20-30% | Evaluate full transcript at session end, not per-message |
| Context window management | 15-25% | Sliding window, summarize older context |
| Response streaming | Latency | Stream tokens to user while generating |

**Model Selection by Task:**
| Task | Model | Reason |
|------|-------|--------|
| AI Conversation (Mode 1) | GPT-4o / Claude Sonnet | Quality matters for user experience |
| Silent Monitoring (Mode 2) | GPT-4o-mini | Background analysis, cost-sensitive |
| Room Moderation (Mode 3) | GPT-4o-mini | Fast decisions, lower complexity |
| Evaluation | GPT-4o | Accuracy matters for scoring |
| Feedback generation | GPT-4o-mini | Formulaic output, cost-sensitive |

**Fallback Chain:**
```
Primary (OpenAI) → Secondary (Anthropic) → Degraded mode (rule-based moderation)
```

---

## 7. Media Pipeline Scaling

### STT Scaling
```
Audio Chunks ──► STT Queue (Redis) ──► STT Worker Pool ──► Deepgram/Whisper API
                                        │  Worker 1  │
                                        │  Worker 2  │
                                        │  Worker N  │
```

- Deepgram streaming API: 1 WebSocket per active speaker
- Max concurrent STT streams = number of active speakers across all sessions
- At 1K sessions × 2 avg speakers = 2K concurrent STT streams
- Deepgram handles this natively; Whisper needs batching

### TTS Scaling
- TTS is triggered only for AI responses (Modes 1 and 3)
- Cache common phrases (greetings, transitions)
- Pre-generate TTS for moderator messages (finite set)
- Queue-based with priority (real-time conversation > feedback)

---

## 8. Deployment Architecture (Kubernetes)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster                           │
│                                                                  │
│  ┌──────────── Namespace: speaking-app ─────────────────────┐   │
│  │                                                           │   │
│  │  Deployments:                                             │   │
│  │    api-gateway      (2-10 pods, HPA)                      │   │
│  │    session-service  (2-20 pods, HPA)                      │   │
│  │    ai-service       (2-15 pods, HPA)                      │   │
│  │    eval-service     (1-5 pods, HPA)                       │   │
│  │    media-service    (2-10 pods, HPA)                      │   │
│  │    worker-service   (2-10 pods, HPA on queue depth)       │   │
│  │                                                           │   │
│  │  StatefulSets:                                            │   │
│  │    postgresql       (1 primary + 2 replicas)              │   │
│  │    redis            (3 masters + 3 replicas)              │   │
│  │                                                           │   │
│  │  Services:                                                │   │
│  │    Ingress (NGINX) → api-gateway ClusterIP                │   │
│  │    Internal ClusterIP for each service                    │   │
│  │                                                           │   │
│  │  ConfigMaps / Secrets:                                    │   │
│  │    LLM API keys, DB credentials, JWT secrets              │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────── Namespace: monitoring ───────────────────────┐   │
│  │    Prometheus + Grafana                                    │   │
│  │    Loki (log aggregation)                                  │   │
│  │    Jaeger (distributed tracing)                            │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Monitoring & Observability

### Key Metrics

| Metric | Alert Threshold |
|--------|----------------|
| WebSocket connections per pod | > 4000 (80% of 5K) |
| API response time (p95) | > 500ms |
| AI response time (p95) | > 3000ms |
| WebSocket message latency (p95) | > 200ms |
| Error rate | > 1% |
| Redis memory usage | > 80% |
| PostgreSQL connection pool | > 80% |
| Celery queue depth | > 500 tasks |
| STT/TTS API error rate | > 5% |
| LLM cost per hour | > budget threshold |

### Dashboards
1. **System Health** — Pod count, CPU, memory, restarts
2. **Real-time Traffic** — Active sessions, connections, messages/sec
3. **AI Performance** — LLM latency, token usage, cost per session
4. **User Experience** — Session duration, error rate, reconnection rate
5. **Business Metrics** — Active users, sessions/day, score distribution

---

## 10. Phased Rollout Plan

### Phase 1: MVP (Single Instance)
```
Target: 100 concurrent users, 50 sessions
- Single server (4 vCPU, 16 GB RAM)
- PostgreSQL (single instance)
- Redis (single instance)
- All services in one FastAPI app (monolith)
- Deploy with Docker Compose
```

### Phase 2: Service Split (Moderate Scale)
```
Target: 1K concurrent users, 500 sessions
- Split into microservices
- Add Redis Pub/Sub for cross-pod WS
- PgBouncer connection pooling
- 2-3 pods per service
- Deploy with Kubernetes
```

### Phase 3: Full Scale
```
Target: 10K+ concurrent users, 5K+ sessions
- Full Kubernetes HPA
- Redis Cluster
- PostgreSQL read replicas + partitioning
- CDN for static + listener audio
- Multi-region (if needed)
```

---

## 11. Cost Estimation (Phase 2, ~1K concurrent users)

| Resource | Specification | Est. Monthly Cost |
|----------|--------------|-------------------|
| Kubernetes (3 nodes) | 4 vCPU, 16 GB each | $350 |
| PostgreSQL (managed) | 4 vCPU, 16 GB, 100 GB SSD | $200 |
| Redis (managed) | 6 GB cluster | $150 |
| S3 / Object Storage | 500 GB | $12 |
| LLM API (OpenAI) | ~2M tokens/day | $600-1200 |
| STT API (Deepgram) | ~500 hours/month | $300 |
| TTS API | ~200 hours/month | $200 |
| NGINX / Load Balancer | Managed | $20 |
| Monitoring (Grafana Cloud) | — | $50 |
| **Total** | | **~$1,900 - $2,500/mo** |

LLM costs dominate. Optimize aggressively with caching, model tiering, and batching.

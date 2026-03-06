# Microservices Breakdown

## Service Map

```
┌─────────────────────────────────────────────────────────────────┐
│                        SERVICES                                  │
│                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐                     │
│  │  api-gateway    │    │  auth-service   │                     │
│  │  Port: 8000     │    │  Port: 8001     │                     │
│  │  Public entry   │    │  JWT + OAuth    │                     │
│  └─────────────────┘    └─────────────────┘                     │
│                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐                     │
│  │  session-service│    │  ai-service     │                     │
│  │  Port: 8002     │    │  Port: 8003     │                     │
│  │  Room + Session │    │  LLM + Eval     │                     │
│  │  management     │    │  orchestration  │                     │
│  └─────────────────┘    └─────────────────┘                     │
│                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐                     │
│  │  eval-service   │    │  media-service  │                     │
│  │  Port: 8004     │    │  Port: 8005     │                     │
│  │  Scoring +      │    │  STT + TTS +    │                     │
│  │  Analytics      │    │  Audio stream   │                     │
│  └─────────────────┘    └─────────────────┘                     │
│                                                                  │
│  ┌─────────────────┐                                             │
│  │  worker-service │  (Celery workers, no HTTP port)             │
│  │  Background     │                                             │
│  │  task processing│                                             │
│  └─────────────────┘                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. API Gateway (`api-gateway`)

**Responsibility**: Single entry point for all client traffic.

| Aspect | Detail |
|--------|--------|
| **Port** | 8000 |
| **Framework** | FastAPI |
| **Owns** | Route dispatch, CORS, rate limiting, request logging |
| **Auth** | Validates JWT on every request (delegates issuance to auth-service) |
| **WebSocket** | Upgrades WS connections, routes to session-service |

**Key routes it proxies:**
```
/api/v1/auth/*      → auth-service
/api/v1/sessions/*  → session-service
/api/v1/ai/*        → ai-service
/api/v1/eval/*      → eval-service
/api/v1/media/*     → media-service
/ws/session/{id}    → session-service (WebSocket upgrade)
```

---

## 2. Auth Service (`auth-service`)

**Responsibility**: User identity, authentication, and authorization.

| Aspect | Detail |
|--------|--------|
| **Port** | 8001 |
| **Database tables** | `users`, `refresh_tokens` |
| **Auth method** | JWT (access + refresh tokens) |
| **OAuth** | Google, GitHub (optional) |
| **Password** | bcrypt hashing |

**Capabilities:**
- User registration & login
- JWT issuance (15min access / 7d refresh)
- Password reset flow
- User profile management
- Role management (admin, user)

---

## 3. Session Service (`session-service`)

**Responsibility**: Core conversation engine. Manages rooms, sessions, participants, and WebSocket connections.

| Aspect | Detail |
|--------|--------|
| **Port** | 8002 |
| **Database tables** | `sessions`, `session_participants`, `messages`, `rooms` |
| **WebSocket** | Primary WS handler for all conversation modes |
| **State** | Redis for active session state (who's connected, speaking turns) |

**Capabilities:**
- Create/join/leave sessions for all 3 modes
- WebSocket connection lifecycle management
- Message routing between participants
- Speaker slot management for public rooms (max 5)
- Listener broadcast (no tracking)
- Transcript assembly and persistence
- Publishes events to Redis for AI/Eval consumption

**Session Modes:**

| Mode | Code | Max Speakers | AI Role | Listeners |
|------|------|-------------|---------|-----------|
| AI Conversation | `ai_1on1` | 1 (+ AI) | Active participant | N/A |
| Peer Monitored | `peer_1on1` | 2 | Silent observer | N/A |
| Public Room | `public_room` | 5 | Moderator | Unlimited |

**Connection Manager (in-memory + Redis):**
```python
# Conceptual structure
active_connections = {
    "session_abc": {
        "speakers": {
            "user_1": WebSocket,
            "user_2": WebSocket,
        },
        "listeners": [WebSocket, WebSocket, ...],  # anonymous
    }
}
```

---

## 4. AI Service (`ai-service`)

**Responsibility**: All LLM interactions — conversation responses, moderation, and analysis.

| Aspect | Detail |
|--------|--------|
| **Port** | 8003 |
| **Database tables** | `ai_interactions` (log of all LLM calls) |
| **LLM Provider** | OpenAI / Anthropic (abstracted behind interface) |
| **Consumes** | Redis events from session-service |
| **Produces** | AI responses, moderation decisions, analysis results |

**Sub-components:**

### 4a. AI Conversation Engine
- Handles Mode 1 (1-to-1 AI chat)
- Maintains conversation context window
- Generates contextual responses
- Adapts difficulty to user level

### 4b. Silent Monitor
- Handles Mode 2 (peer conversation monitoring)
- Consumes transcript stream via Redis
- Produces periodic silent analysis (not sent to users during session)
- Generates post-session feedback

### 4c. Room Moderator
- Handles Mode 3 (public room)
- Monitors all speaker messages in real-time
- Intervenes for: off-topic drift, inappropriate content, turn-taking fairness
- Suggests discussion topics
- Manages speaking queue

**LLM Abstraction Layer:**
```python
class LLMProvider(Protocol):
    async def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse: ...
    async def stream(self, messages: list[Message], config: LLMConfig) -> AsyncIterator[str]: ...

class OpenAIProvider(LLMProvider): ...
class AnthropicProvider(LLMProvider): ...
```

---

## 5. Evaluation Service (`eval-service`)

**Responsibility**: Skill assessment, scoring, and progress analytics.

| Aspect | Detail |
|--------|--------|
| **Port** | 8004 |
| **Database tables** | `evaluations`, `skill_scores`, `progress_snapshots` |
| **Consumes** | Transcript data + AI analysis results |
| **Produces** | Scores, feedback, progress metrics |

**Evaluation Dimensions:**

| Skill | What's Measured | Scoring Method |
|-------|----------------|----------------|
| **Speaking** | Fluency, pronunciation, vocabulary, coherence, filler words | STT confidence + LLM analysis |
| **Listening** | Comprehension accuracy, response relevance, follow-up quality | LLM analysis of response-to-prompt alignment |
| **Writing** | Grammar, spelling, vocabulary range, coherence, structure | LLM analysis of text messages |

**Scoring Scale:** 0–100 per dimension, computed as weighted composite.

```
speaking_score = (
    fluency * 0.25 +
    pronunciation * 0.20 +
    vocabulary * 0.20 +
    coherence * 0.20 +
    filler_penalty * 0.15
)
```

**Progress Tracking:**
- Per-session scores stored
- Rolling averages (7d, 30d, all-time)
- Skill-level classification: Beginner (0-30), Intermediate (31-60), Advanced (61-85), Expert (86-100)

---

## 6. Media Service (`media-service`)

**Responsibility**: Audio processing pipeline — Speech-to-Text, Text-to-Speech, audio storage.

| Aspect | Detail |
|--------|--------|
| **Port** | 8005 |
| **STT** | OpenAI Whisper API / Deepgram (streaming) |
| **TTS** | OpenAI TTS / ElevenLabs |
| **Storage** | S3/MinIO for audio recordings |

**Audio Pipeline:**
```
User Mic → WebSocket (binary frames) → Media Service
    │
    ├──► STT Engine → Text transcript → Session Service
    │
    └──► Audio Buffer → S3 Storage (if recording enabled)

AI Response Text → Media Service → TTS Engine → Audio → WebSocket → User Speaker
```

**Streaming STT:**
- Audio chunks received via WebSocket
- Streamed to STT provider in real-time
- Interim results sent back for live captioning
- Final results committed to transcript

---

## 7. Worker Service (`worker-service`)

**Responsibility**: Async background tasks via Celery + Redis.

| Task | Trigger | Description |
|------|---------|-------------|
| `evaluate_session` | Session end | Run full evaluation pipeline on transcript |
| `generate_feedback` | Evaluation complete | Generate detailed LLM-powered feedback |
| `compute_progress` | New scores | Update rolling averages and snapshots |
| `cleanup_stale_sessions` | Cron (every 5min) | Close zombie sessions |
| `export_transcript` | User request | Generate PDF/JSON transcript export |
| `aggregate_analytics` | Cron (daily) | Compute platform-wide analytics |

---

## Inter-Service Communication

```
┌──────────────────────────────────────────────────────────────┐
│                    Communication Patterns                      │
│                                                                │
│  Synchronous (HTTP):                                          │
│    api-gateway ──► auth-service    (JWT validation)           │
│    session-service ──► ai-service  (AI response needed NOW)   │
│                                                                │
│  Asynchronous (Redis Pub/Sub):                                │
│    session-service ──pub──► ai-service      (transcript events)│
│    session-service ──pub──► eval-service    (session ended)    │
│    ai-service ──pub──► eval-service         (analysis ready)   │
│    eval-service ──pub──► worker-service     (compute progress) │
│                                                                │
│  Task Queue (Celery + Redis):                                 │
│    Any service ──enqueue──► worker-service  (background work)  │
└──────────────────────────────────────────────────────────────┘
```

**Redis Pub/Sub Channels:**
```
channel: session.{session_id}.messages     — new message in session
channel: session.{session_id}.ended        — session completed
channel: ai.{session_id}.response          — AI generated response
channel: ai.{session_id}.moderation        — moderator action
channel: eval.{session_id}.scores          — evaluation complete
```

---

## Service Dependencies

```
api-gateway
  ├── auth-service
  ├── session-service
  │     ├── ai-service
  │     ├── media-service
  │     └── Redis (state)
  ├── eval-service
  │     └── ai-service (for LLM-based evaluation)
  └── media-service
        └── External STT/TTS APIs

worker-service
  ├── eval-service (calls evaluation APIs)
  ├── ai-service (calls LLM for feedback generation)
  └── PostgreSQL + Redis + S3
```

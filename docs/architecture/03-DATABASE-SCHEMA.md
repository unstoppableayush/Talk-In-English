# Database Schema Design

## Overview

PostgreSQL is the primary data store. Each service logically owns its tables but they share a single PostgreSQL instance (can be split later for independent scaling).

**Schema namespaces:**
- `auth.*` — Auth Service
- `sessions.*` — Session Service
- `ai.*` — AI Service
- `eval.*` — Evaluation Service

---

## Entity Relationship Diagram

```
┌─────────────┐       ┌──────────────────┐       ┌─────────────────┐
│   users     │       │    sessions      │       │     rooms       │
│─────────────│       │──────────────────│       │─────────────────│
│ id (PK)     │◄──┐   │ id (PK)          │   ┌──►│ id (PK)         │
│ email       │   │   │ room_id (FK)     │───┘   │ name            │
│ display_name│   │   │ mode             │       │ topic           │
│ password_h  │   │   │ status           │       │ max_speakers    │
│ role        │   │   │ created_by (FK)  │───┐   │ created_by (FK) │
│ level       │   │   │ started_at       │   │   │ is_active       │
│ created_at  │   │   │ ended_at         │   │   │ created_at      │
│ updated_at  │   │   │ config (JSONB)   │   │   └─────────────────┘
└─────────────┘   │   └──────────────────┘   │
      ▲           │            │              │
      │           │            │              │
      │   ┌───────┴────────────┼──────────────┘
      │   │                    │
      │   │                    ▼
      │   │   ┌────────────────────────┐      ┌──────────────────────┐
      │   │   │ session_participants   │      │      messages        │
      │   │   │────────────────────────│      │──────────────────────│
      │   └──►│ id (PK)               │      │ id (PK)              │
      │       │ session_id (FK)        │      │ session_id (FK)      │
      └───────│ user_id (FK)           │      │ sender_id (FK|NULL)  │
              │ role (speaker|listener)│   ┌──│ sender_type          │
              │ joined_at             │   │  │ content              │
              │ left_at               │   │  │ message_type         │
              │ is_active             │   │  │ audio_url            │
              └────────────────────────┘   │  │ metadata (JSONB)     │
                                          │  │ created_at           │
      ┌───────────────────────────────────┘  └──────────────────────┘
      │
      │   ┌──────────────────────┐       ┌──────────────────────┐
      │   │   evaluations        │       │   skill_scores       │
      │   │──────────────────────│       │──────────────────────│
      │   │ id (PK)              │◄──────│ id (PK)              │
      ├──►│ session_id (FK)      │       │ evaluation_id (FK)   │
      │   │ user_id (FK)         │       │ skill_type           │
      │   │ overall_score        │       │ score                │
      │   │ feedback (TEXT)      │       │ sub_scores (JSONB)   │
      │   │ evaluated_at         │       │ feedback (TEXT)       │
      │   └──────────────────────┘       └──────────────────────┘
      │
      │   ┌──────────────────────┐       ┌──────────────────────┐
      │   │ progress_snapshots   │       │   ai_interactions    │
      │   │──────────────────────│       │──────────────────────│
      │   │ id (PK)              │       │ id (PK)              │
      └──►│ user_id (FK)         │       │ session_id (FK)      │
          │ snapshot_date        │       │ interaction_type     │
          │ speaking_avg         │       │ prompt_tokens        │
          │ listening_avg        │       │ completion_tokens    │
          │ writing_avg          │       │ model                │
          │ overall_avg          │       │ latency_ms           │
          │ sessions_count       │       │ created_at           │
          │ period (7d|30d|all)  │       └──────────────────────┘
          └──────────────────────┘
```

---

## Table Definitions

### `auth.users`
```sql
CREATE TABLE auth.users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    display_name    VARCHAR(100) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    avatar_url      VARCHAR(500),
    role            VARCHAR(20) NOT NULL DEFAULT 'user'
                    CHECK (role IN ('user', 'admin')),
    level           VARCHAR(20) NOT NULL DEFAULT 'beginner'
                    CHECK (level IN ('beginner', 'intermediate', 'advanced', 'expert')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON auth.users(email);
```

### `auth.refresh_tokens`
```sql
CREATE TABLE auth.refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL UNIQUE,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ
);

CREATE INDEX idx_refresh_tokens_user ON auth.refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires ON auth.refresh_tokens(expires_at);
```

### `sessions.rooms`
```sql
CREATE TABLE sessions.rooms (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(200) NOT NULL,
    topic           TEXT,
    description     TEXT,
    max_speakers    INT NOT NULL DEFAULT 5 CHECK (max_speakers BETWEEN 2 AND 5),
    created_by      UUID NOT NULL REFERENCES auth.users(id),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    config          JSONB NOT NULL DEFAULT '{}',
    -- config: { "language": "en", "difficulty": "intermediate", "ai_moderation_level": "standard" }
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rooms_active ON sessions.rooms(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_rooms_created_by ON sessions.rooms(created_by);
```

### `sessions.sessions`
```sql
CREATE TABLE sessions.sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id         UUID REFERENCES sessions.rooms(id),
    -- room_id is NULL for 1-on-1 modes (ai_1on1, peer_1on1)
    mode            VARCHAR(20) NOT NULL
                    CHECK (mode IN ('ai_1on1', 'peer_1on1', 'public_room')),
    status          VARCHAR(20) NOT NULL DEFAULT 'waiting'
                    CHECK (status IN ('waiting', 'active', 'completed', 'cancelled')),
    created_by      UUID NOT NULL REFERENCES auth.users(id),
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    duration_sec    INT,  -- computed on session end
    config          JSONB NOT NULL DEFAULT '{}',
    -- config: { "language": "en", "topic": "...", "difficulty": "intermediate" }
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_status ON sessions.sessions(status);
CREATE INDEX idx_sessions_mode ON sessions.sessions(mode);
CREATE INDEX idx_sessions_created_by ON sessions.sessions(created_by);
CREATE INDEX idx_sessions_room ON sessions.sessions(room_id) WHERE room_id IS NOT NULL;
CREATE INDEX idx_sessions_created_at ON sessions.sessions(created_at DESC);
```

### `sessions.session_participants`
```sql
CREATE TABLE sessions.session_participants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES sessions.sessions(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES auth.users(id),
    role            VARCHAR(20) NOT NULL DEFAULT 'speaker'
                    CHECK (role IN ('speaker', 'listener')),
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at         TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,

    UNIQUE(session_id, user_id)
);

-- NOTE: Listeners in public rooms are NOT stored here.
-- Only speakers are tracked as participants.
-- Listeners connect via WebSocket and receive broadcasts but have no DB record.

CREATE INDEX idx_participants_session ON sessions.session_participants(session_id);
CREATE INDEX idx_participants_user ON sessions.session_participants(user_id);
CREATE INDEX idx_participants_active ON sessions.session_participants(session_id, is_active)
    WHERE is_active = TRUE;
```

### `sessions.messages`
```sql
CREATE TABLE sessions.messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES sessions.sessions(id) ON DELETE CASCADE,
    sender_id       UUID REFERENCES auth.users(id),
    -- sender_id is NULL for system/AI messages
    sender_type     VARCHAR(20) NOT NULL
                    CHECK (sender_type IN ('user', 'ai', 'system', 'moderator')),
    content         TEXT NOT NULL,
    message_type    VARCHAR(20) NOT NULL DEFAULT 'text'
                    CHECK (message_type IN ('text', 'audio', 'mixed')),
    audio_url       VARCHAR(500),
    -- S3 URL if audio was recorded
    stt_confidence  FLOAT,
    -- STT confidence score (0.0 - 1.0) if transcribed from audio
    metadata        JSONB NOT NULL DEFAULT '{}',
    -- metadata: { "word_count": 42, "language_detected": "en", "duration_ms": 3200 }
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_session ON sessions.messages(session_id, created_at);
CREATE INDEX idx_messages_sender ON sessions.messages(sender_id) WHERE sender_id IS NOT NULL;

-- Partition by month for high-volume message tables
-- (implement when table exceeds ~10M rows)
```

### `eval.evaluations`
```sql
CREATE TABLE eval.evaluations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES sessions.sessions(id),
    user_id         UUID NOT NULL REFERENCES auth.users(id),
    overall_score   FLOAT NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
    feedback        TEXT,
    -- LLM-generated natural language feedback
    raw_analysis    JSONB NOT NULL DEFAULT '{}',
    -- Full LLM analysis output for debugging/auditing
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(session_id, user_id)
);

CREATE INDEX idx_evaluations_user ON eval.evaluations(user_id, evaluated_at DESC);
CREATE INDEX idx_evaluations_session ON eval.evaluations(session_id);
```

### `eval.skill_scores`
```sql
CREATE TABLE eval.skill_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id   UUID NOT NULL REFERENCES eval.evaluations(id) ON DELETE CASCADE,
    skill_type      VARCHAR(20) NOT NULL
                    CHECK (skill_type IN ('speaking', 'listening', 'writing')),
    score           FLOAT NOT NULL CHECK (score BETWEEN 0 AND 100),
    sub_scores      JSONB NOT NULL DEFAULT '{}',
    -- speaking: { "fluency": 82, "pronunciation": 75, "vocabulary": 88, "coherence": 79, "filler_words": 90 }
    -- listening: { "comprehension": 85, "response_relevance": 78, "follow_up_quality": 82 }
    -- writing: { "grammar": 90, "spelling": 95, "vocabulary_range": 80, "coherence": 85, "structure": 88 }
    feedback        TEXT,

    UNIQUE(evaluation_id, skill_type)
);

CREATE INDEX idx_skill_scores_evaluation ON eval.skill_scores(evaluation_id);
```

### `eval.progress_snapshots`
```sql
CREATE TABLE eval.progress_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id),
    snapshot_date   DATE NOT NULL,
    period          VARCHAR(10) NOT NULL
                    CHECK (period IN ('7d', '30d', 'all')),
    speaking_avg    FLOAT CHECK (speaking_avg BETWEEN 0 AND 100),
    listening_avg   FLOAT CHECK (listening_avg BETWEEN 0 AND 100),
    writing_avg     FLOAT CHECK (writing_avg BETWEEN 0 AND 100),
    overall_avg     FLOAT CHECK (overall_avg BETWEEN 0 AND 100),
    sessions_count  INT NOT NULL DEFAULT 0,
    total_duration  INT NOT NULL DEFAULT 0,  -- seconds
    metadata        JSONB NOT NULL DEFAULT '{}',

    UNIQUE(user_id, snapshot_date, period)
);

CREATE INDEX idx_progress_user_date ON eval.progress_snapshots(user_id, snapshot_date DESC);
CREATE INDEX idx_progress_period ON eval.progress_snapshots(period, snapshot_date DESC);
```

### `ai.ai_interactions`
```sql
CREATE TABLE ai.ai_interactions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID REFERENCES sessions.sessions(id),
    interaction_type    VARCHAR(30) NOT NULL
                        CHECK (interaction_type IN (
                            'conversation', 'moderation', 'evaluation',
                            'feedback', 'topic_suggestion'
                        )),
    model               VARCHAR(50) NOT NULL,
    prompt_tokens       INT NOT NULL DEFAULT 0,
    completion_tokens   INT NOT NULL DEFAULT 0,
    total_tokens        INT GENERATED ALWAYS AS (prompt_tokens + completion_tokens) STORED,
    latency_ms          INT,
    cost_usd            NUMERIC(10, 6),
    error               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ai_interactions_session ON ai.ai_interactions(session_id);
CREATE INDEX idx_ai_interactions_type ON ai.ai_interactions(interaction_type, created_at DESC);
CREATE INDEX idx_ai_interactions_cost ON ai.ai_interactions(created_at DESC);
-- Useful for monitoring LLM costs over time
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **UUIDs as PKs** | Safe for distributed systems, no sequential ID leakage |
| **JSONB for flexible fields** | Evaluation sub-scores and config evolve without migrations |
| **Listeners NOT in DB** | Requirement says unlimited, untracked — no write amplification |
| **Separate schemas per service** | Logical ownership boundaries, easy to split DBs later |
| **Soft deletes (is_active)** | Preserve data integrity for analytics |
| **Messages not partitioned initially** | Add monthly partitioning when volume warrants it |
| **Evaluation per session+user** | One evaluation record per user per session, with skill breakdowns |

---

## Indexes Strategy

- **Primary access patterns** indexed: user lookups, session queries, chronological message retrieval
- **Partial indexes** where appropriate (e.g., only active sessions, only active participants)
- **Composite indexes** for common multi-column queries
- **No over-indexing** — add as query patterns emerge from monitoring

---

## Migration Strategy

Use **Alembic** for schema migrations:
```
migrations/
├── versions/
│   ├── 001_create_auth_schema.py
│   ├── 002_create_sessions_schema.py
│   ├── 003_create_eval_schema.py
│   └── 004_create_ai_schema.py
├── env.py
└── alembic.ini
```

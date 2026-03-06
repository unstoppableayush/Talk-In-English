# Speaking App — Backend

FastAPI backend powering the Speaking App. Handles authentication, real-time conversations, AI integration, speech processing, and session evaluation.

---

## Table of Contents

- [Folder Structure](#folder-structure)
- [Build Phases — What Was Built & Where](#build-phases)
- [API Reference (All Endpoints)](#api-reference)
- [WebSocket Endpoints](#websocket-endpoints)
- [Database Models](#database-models)
- [AI / LLM Multi-Provider System](#ai--llm-multi-provider-system)
- [TTS Multi-Provider System](#tts-multi-provider-system)
- [Services Layer](#services-layer)
- [Middleware Stack](#middleware-stack)
- [Configuration (.env)](#configuration)
- [Setup & Run](#setup--run)
- [Troubleshooting](#troubleshooting)

---

## Folder Structure

```
backend/
├── app/
│   ├── main.py                      # FastAPI app factory, lifespan, middleware + router wiring
│   ├── __init__.py
│   │
│   ├── api/                         # REST endpoint routers (each file = 1 router)
│   │   ├── auth.py                  # Register, login, refresh, me
│   │   ├── sessions.py              # Session CRUD, history
│   │   ├── rooms.py                 # Room CRUD, join/leave, end session (+ auto-scoring)
│   │   ├── evaluations.py           # Trigger scoring, get scores/feedback
│   │   ├── progress.py              # Dashboard stats, rolling averages, snapshots
│   │   ├── section_tests.py         # Test CRUD (admin), attempt submission, AI grading
│   │   ├── leaderboard.py           # Weekly/monthly/alltime leaderboard, weakness analysis
│   │   ├── roleplay.py              # Roleplay scenarios, sessions, messages, reports
│   │   └── __init__.py
│   │
│   ├── core/                        # Framework-level infrastructure
│   │   ├── config.py                # Pydantic Settings — all env vars with defaults
│   │   ├── database.py              # SQLAlchemy async engine + session factory
│   │   ├── security.py              # JWT encode/decode, password hashing, token deps
│   │   ├── deps.py                  # FastAPI dependency injection (get_db, get_current_user, require_role)
│   │   ├── middleware.py            # RequestID, SecurityHeaders, RequestLogging, RateLimit
│   │   ├── logging_config.py        # Structured JSON logging (prod) / readable (dev)
│   │   └── __init__.py
│   │
│   ├── models/                      # SQLAlchemy ORM models (mapped to PostgreSQL schemas)
│   │   ├── user.py                  # User model                    → schema: auth
│   │   ├── session.py               # Session, SessionParticipant   → schema: sessions
│   │   ├── message.py               # Message (chat/system/ai)      → schema: sessions
│   │   ├── evaluation.py            # SessionScore                  → schema: eval
│   │   ├── ai_feedback.py           # AIFeedbackReport              → schema: eval
│   │   ├── ai_interaction.py        # AIInteractionLog              → schema: ai
│   │   ├── leaderboard.py           # LeaderboardEntry              → schema: eval
│   │   ├── section_test.py          # TestDefinition, TestAttempt   → schema: eval
│   │   ├── roleplay.py              # RoleplayScenario, Session, Message, Evaluation → schema: ai
│   │   └── __init__.py
│   │
│   ├── schemas/                     # Pydantic request/response schemas
│   │   ├── models.py                # ALL schemas in one file (User, Room, Session, Score, Roleplay, etc.)
│   │   └── __init__.py
│   │
│   ├── services/                    # Business logic / AI engines
│   │   ├── ai_service.py            # LLM abstraction + fallback, ConversationManager, ModerationService, ScoringEngine
│   │   ├── speech_service.py        # Deepgram STT, TTS fallback (ElevenLabs/OpenAI), PronunciationAnalyzer
│   │   ├── roleplay_service.py      # RoleplayEngine — AI conversation + session evaluation
│   │   └── __init__.py
│   │
│   ├── ws/                          # WebSocket handlers
│   │   ├── connection_manager.py    # ConnectionManager with Redis pub/sub for scaling
│   │   ├── handler.py               # Main chat WS — AI 1-on-1, peer chat, public room
│   │   ├── audio_handler.py         # Audio streaming WS — STT + TTS pipeline
│   │   ├── roleplay_handler.py      # Roleplay WS — real-time AI roleplay conversation
│   │   └── __init__.py              # Aggregates all WS routers
│   │
│   ├── workers/                     # Celery background tasks (placeholder)
│   │   └── __init__.py
│   │
│   └── scripts/                     # CLI utilities
│       ├── seed_scenarios.py        # Seed 6 predefined roleplay scenarios
│       └── __init__.py
│
├── migrations/
│   ├── init.sql                     # Creates PG schemas (auth, sessions, eval, ai) + pgcrypto
│   └── 001_full_schema.sql          # Complete table definitions for all models
│
├── tests/                           # Test directory
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Production image (Python 3.12, non-root, 4 workers)
└── .dockerignore
```

---

## Build Phases

### Phase 1 — Architecture Design
**What:** System design documents, technology decisions, scalability strategy.
**Files:** `docs/architecture/01-HIGH-LEVEL-ARCHITECTURE.md` through `06-SCALABILITY-STRATEGY.md`

### Phase 2 — Database Schema
**What:** PostgreSQL schema with 4 namespaces, UUID PKs, JSONB fields, CHECK constraints.
**Files:**
- `migrations/init.sql` — Creates schemas: `auth`, `sessions`, `eval`, `ai`
- `migrations/001_full_schema.sql` — All table DDL
- `app/models/*.py` — SQLAlchemy ORM models

### Phase 3 — Backend Core (FastAPI)
**What:** App factory, auth system (JWT + bcrypt + RBAC), middleware stack, dependency injection.
**Files:**
- `app/main.py` — App factory with lifespan (Redis init, logging)
- `app/core/config.py` — All environment variables with `pydantic-settings`
- `app/core/security.py` — JWT creation/verification, password hashing
- `app/core/deps.py` — `get_db`, `get_current_user`, `require_role("admin")` factory
- `app/core/middleware.py` — 4 middleware layers (RequestID → SecurityHeaders → Logging → RateLimit)
- `app/api/auth.py` — `POST /register`, `POST /login`, `POST /refresh`, `GET /me`
- `app/api/sessions.py` — Session CRUD + history
- `app/api/rooms.py` — Room CRUD + join/leave + auto-scoring on end

### Phase 4 — AI Integration
**What:** LLM abstraction layer, conversation manager, moderation service, scoring engine.
**Files:**
- `app/services/ai_service.py` — **The core AI file.** Contains:
  - `LLMProvider` abstract class + `OpenAIProvider`, `GrokProvider`, `GeminiProvider`, `DeepSeekProvider`
  - `FallbackLLMProvider` — tries providers in order, auto-switches on failure
  - `ConversationManager` — per-session context memory for AI 1-on-1 chats
  - `ModerationService` — real-time group discussion moderation
  - `ScoringEngine` — end-of-session AI evaluation (8 dimensions, 0-100 each)
  - Prompt templates: `CONVERSATION_SYSTEM_PROMPT`, `MODERATION_SYSTEM_PROMPT`, `EVALUATION_SYSTEM_PROMPT`

### Phase 5 — Speech Processing
**What:** Deepgram STT streaming, TTS with ElevenLabs/OpenAI fallback, pronunciation analysis.
**Files:**
- `app/services/speech_service.py` — Contains:
  - `DeepgramSTT` — real-time WebSocket audio streaming to Deepgram Nova-2
  - `ElevenLabsTTS` — high-quality TTS via ElevenLabs API
  - `OpenAITTS` — fallback TTS via OpenAI
  - `FallbackTTS` — tries ElevenLabs first, falls back to OpenAI
  - `PronunciationAnalyzer` — scores per-word confidence from STT results
- `app/ws/audio_handler.py` — WebSocket endpoint for real-time audio streaming

### Phase 6 — (Frontend — see frontend README)

### Phase 7 — Silent AI Monitoring
**What:** Auto-trigger AI evaluation when peer/public sessions end.
**Files:**
- `app/api/rooms.py` — `end_room_session()` now runs `scoring_engine.evaluate_session()` as a `BackgroundTask` for `peer_1on1` and `public_room` modes

### Phase 8 — Section Testing API
**What:** Admin-created tests with AI-powered grading.
**Files:**
- `app/api/section_tests.py` — Full CRUD:
  - `POST /tests` (admin-only) — create test definition
  - `GET /tests` — list with section/difficulty/language filters
  - `GET /tests/{id}` — single test
  - `POST /tests/{id}/attempt` — submit answers, AI grades in background
  - `GET /tests/attempts/me` — user's attempt history
- `app/models/section_test.py` — `TestDefinition`, `TestAttempt` models

### Phase 9 — Analytics & Leaderboard
**What:** Ranked leaderboards, personal rank, weakness analysis.
**Files:**
- `app/api/leaderboard.py`:
  - `GET /leaderboard?period=weekly|monthly|alltime` — top users by XP
  - `GET /leaderboard/me` — personal rank + surrounding users
  - `GET /leaderboard/weakness-analysis` — bottom-3 skill dimensions + improvement tips
- `app/models/leaderboard.py` — `LeaderboardEntry` model

### Phase 10 — Deployment & Production
**What:** Docker builds, nginx reverse proxy, production compose.
**Files:**
- `Dockerfile` — Multi-stage Python 3.12 image, non-root user, 4 uvicorn workers
- `../docker-compose.prod.yml` — Postgres, Redis, backend (2 replicas), frontend, nginx
- `../nginx/nginx.conf` — Reverse proxy with API/WS routing, rate limiting, gzip, security headers
- `app/core/logging_config.py` — Structured JSON logging for production

### Phase 11 — AI Role-Play Speaking Module
**What:** Full conversational roleplay system with scenarios, real-time chat, and AI evaluation.
**Files:**
- `app/models/roleplay.py` — 4 models: `RoleplayScenario`, `RoleplaySession`, `RoleplayMessage`, `RoleplayEvaluation`
- `app/schemas/models.py` — 6 Pydantic schemas added (search for "Roleplay" in file)
- `app/services/roleplay_service.py` — `RoleplayEngine`:
  - `create_context()` / `remove_context()` — per-session lifecycle
  - `generate_reply()` — builds context, calls LLM, returns AI reply
  - `evaluate_session()` — analyzes transcript, scores 7 dimensions, awards XP
  - `ROLEPLAY_SYSTEM_PROMPT` / `ROLEPLAY_EVAL_PROMPT` — prompt templates
- `app/api/roleplay.py` — 7 REST endpoints (see API Reference below)
- `app/ws/roleplay_handler.py` — WebSocket for real-time roleplay conversation
- `app/scripts/seed_scenarios.py` — Seeds 6 predefined scenarios

### Multi-Provider LLM + TTS (Cross-cutting)
**What:** Support for OpenAI, Grok (xAI), Gemini (Google), DeepSeek with automatic fallback. ElevenLabs TTS as primary voice.
**Files:**
- `app/core/config.py` — Added all API key settings + `LLM_PROVIDER_ORDER`, `TTS_PROVIDER_ORDER`
- `app/services/ai_service.py` — 4 LLM provider classes + `FallbackLLMProvider`
- `app/services/speech_service.py` — `ElevenLabsTTS` + `FallbackTTS`

---

## API Reference

All REST endpoints are prefixed with `/api/v1`.

### Auth — `/api/v1/auth`
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/register` | Create account | No |
| POST | `/login` | Get JWT tokens | No |
| POST | `/refresh` | Refresh access token | No |
| GET | `/me` | Current user profile | Yes |

### Sessions — `/api/v1/sessions`
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/` | List user's sessions | Yes |
| GET | `/{id}` | Session details | Yes |

### Rooms — `/api/v1/rooms`
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/` | Create room | Yes |
| GET | `/` | List active rooms | Yes |
| GET | `/{id}` | Room details | Yes |
| POST | `/{id}/join` | Join as speaker/listener | Yes |
| POST | `/{id}/leave` | Leave room | Yes |
| POST | `/{id}/end` | End session (triggers AI scoring for peer/public) | Yes |

### Evaluations — `/api/v1/eval`
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/sessions/{id}/evaluate` | Manually trigger AI scoring | Yes |
| GET | `/sessions/{id}/scores` | Get session scores | Yes |
| GET | `/sessions/{id}/feedback` | Get AI feedback report | Yes |

### Progress — `/api/v1/progress`
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/dashboard` | XP, streak, session count, dimension averages | Yes |
| GET | `/history` | Score history with snapshots | Yes |

### Section Tests — `/api/v1/tests`
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/` | Create test (admin only) | Admin |
| GET | `/` | List tests (filter by section/difficulty/language) | Yes |
| GET | `/{id}` | Test details | Yes |
| POST | `/{id}/attempt` | Submit answers → AI grading in background | Yes |
| GET | `/attempts/me` | User's attempt history | Yes |

### Leaderboard — `/api/v1/leaderboard`
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/` | Top users (weekly/monthly/alltime) | Yes |
| GET | `/me` | Personal rank + context | Yes |
| GET | `/weakness-analysis` | Bottom-3 dimensions + tips | Yes |

### Roleplay — `/api/v1/roleplay`
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/scenarios` | List predefined scenarios (filter by category/difficulty/language) | Yes |
| POST | `/start-session` | Start roleplay (scenario or custom topic) | Yes |
| POST | `/send-message?session_id=` | Send message, get AI reply | Yes |
| POST | `/end-session/{session_id}` | End session + trigger evaluation | Yes |
| GET | `/report/{session_id}` | Get evaluation report | Yes |
| GET | `/sessions` | User's roleplay session history | Yes |
| GET | `/sessions/{session_id}/messages` | Full conversation transcript | Yes |

---

## WebSocket Endpoints

All at `/ws/...`. Require `?token=<JWT>` query parameter.

| Endpoint | Description | File |
|----------|-------------|------|
| `/ws/{session_id}` | Main chat — AI 1-on-1, peer, public room | `ws/handler.py` |
| `/ws/audio/{session_id}` | Audio streaming — STT ↔ TTS pipeline | `ws/audio_handler.py` |
| `/ws/roleplay/{session_id}` | Real-time roleplay conversation | `ws/roleplay_handler.py` |

### Roleplay WS Protocol
```
Client → Server:  {"event": "roleplay.message", "data": {"content": "Hello"}}
Server → Client:  {"event": "roleplay.ai_reply", "data": {"id": "...", "content": "...", "created_at": "..."}}
Client → Server:  {"event": "roleplay.end", "data": {}}
Server → Client:  {"event": "roleplay.ended", "data": {"session_id": "...", "status": "completed"}}
```

---

## Database Models

4 PostgreSQL schemas:

| Schema | Models | Purpose |
|--------|--------|---------|
| `auth` | User | Accounts, credentials, XP, streaks |
| `sessions` | Session, SessionParticipant, Message | Rooms, participants, chat history |
| `eval` | SessionScore, AIFeedbackReport, LeaderboardEntry, TestDefinition, TestAttempt | Scoring, feedback, ranking, tests |
| `ai` | AIInteractionLog, RoleplayScenario, RoleplaySession, RoleplayMessage, RoleplayEvaluation | AI logs, roleplay system |

---

## AI / LLM Multi-Provider System

Configured in `app/services/ai_service.py`. The `FallbackLLMProvider` tries each provider in order:

| Priority (default) | Provider | Model | API Base |
|---------------------|----------|-------|----------|
| 1 | OpenAI | gpt-4o | `api.openai.com` |
| 2 | Grok (xAI) | grok-3-latest | `api.x.ai/v1` |
| 3 | Gemini (Google) | gemini-2.0-flash | `generativelanguage.googleapis.com/v1beta/openai/` |
| 4 | DeepSeek | deepseek-chat | `api.deepseek.com` |

**How it works:**
1. On startup, checks which API keys are present in `.env`
2. Skips providers with no key
3. On each API call, tries the first provider
4. If it fails (rate limit, quota, network error), automatically tries the next
5. Logs each fallback event

**Change priority:** Set `LLM_PROVIDER_ORDER=deepseek,openai,gemini` in `.env`

---

## TTS Multi-Provider System

Configured in `app/services/speech_service.py`. The `FallbackTTS` prefers ElevenLabs:

| Priority (default) | Provider | Why |
|---------------------|----------|-----|
| 1 | ElevenLabs | Natural, expressive, multilingual v2 — best quality |
| 2 | OpenAI TTS | Functional fallback (tts-1 model) |

**Change priority:** Set `TTS_PROVIDER_ORDER=openai,elevenlabs` in `.env`

---

## Services Layer

| Service | File | Singleton | Purpose |
|---------|------|-----------|---------|
| `llm_provider` | `ai_service.py` | `FallbackLLMProvider` | All LLM calls go through this |
| `conversation_manager` | `ai_service.py` | `ConversationManager` | AI 1-on-1 session context |
| `moderation_service` | `ai_service.py` | `ModerationService` | Public room AI moderation |
| `scoring_engine` | `ai_service.py` | `ScoringEngine` | Post-session evaluation |
| `roleplay_engine` | `roleplay_service.py` | `RoleplayEngine` | Roleplay AI conversation + evaluation |
| `stt_service` | `speech_service.py` | `DeepgramSTT` | Speech-to-text |
| `tts_service` | `speech_service.py` | `FallbackTTS` | Text-to-speech |
| `pronunciation_analyzer` | `speech_service.py` | `PronunciationAnalyzer` | Word-level pronunciation scoring |

---

## Middleware Stack

Applied in order (outermost → innermost) in `main.py`:

1. **RequestIdMiddleware** — Adds `X-Request-ID` header to every request
2. **SecurityHeadersMiddleware** — XSS protection, content-type nosniff, etc.
3. **RequestLoggingMiddleware** — Logs method, path, status, duration
4. **RateLimitMiddleware** — 100 requests/minute per IP
5. **CORSMiddleware** — Configurable origins

---

## Configuration

All settings live in `app/core/config.py` and are loaded from environment variables (`.env` file).

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | Local dev URL | PostgreSQL connection string |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis for pub/sub |
| `JWT_SECRET` | **Yes (production)** | `dev-secret-...` | Token signing key |
| `OPENAI_API_KEY` | At least 1 LLM key | `""` | OpenAI API key |
| `GROK_API_KEY` | Optional | `""` | xAI Grok API key |
| `GEMINI_API_KEY` | Optional | `""` | Google Gemini API key |
| `DEEPSEEK_API_KEY` | Optional | `""` | DeepSeek API key |
| `LLM_PROVIDER_ORDER` | No | `openai,grok,gemini,deepseek` | Priority order |
| `ELEVENLABS_API_KEY` | Optional | `""` | ElevenLabs TTS key |
| `ELEVENLABS_VOICE_ID` | No | `21m00Tcm4TlvDq8ikWAM` | Voice ID |
| `TTS_PROVIDER_ORDER` | No | `elevenlabs,openai` | TTS priority |
| `DEEPGRAM_API_KEY` | For STT | `""` | Deepgram key |
| `ENVIRONMENT` | No | `development` | `development` / `production` |

---

## Setup & Run

### Local Development

```bash
# 1. Start Postgres + Redis
docker-compose up -d postgres redis

# 2. Setup Python env
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt

# 3. Create .env file
copy ..\.env.example .env
# Edit .env — add at least one LLM API key

# 4. Run database migrations
psql -U speaking_app -d speaking_app -f migrations/init.sql
psql -U speaking_app -d speaking_app -f migrations/001_full_schema.sql

# 5. Seed roleplay scenarios
python -m app.scripts.seed_scenarios

# 6. Start server
uvicorn app.main:app --reload --port 8000
```

### With Docker

```bash
docker-compose up
# Backend at http://localhost:8000
# API docs at http://localhost:8000/api/docs
```

### Production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## Troubleshooting

| Problem | Where to Look | Fix |
|---------|---------------|-----|
| "All LLM providers failed" | `ai_service.py` → `FallbackLLMProvider` | Check at least 1 API key is set in `.env` |
| "All TTS providers failed" | `speech_service.py` → `FallbackTTS` | Check `ELEVENLABS_API_KEY` or `OPENAI_API_KEY` |
| JWT 401 errors | `core/security.py` → `decode_token()` | Check `JWT_SECRET` matches, token not expired |
| WebSocket won't connect | `ws/handler.py` or `ws/roleplay_handler.py` | Pass `?token=<jwt>` as query param |
| Room scoring not triggered | `api/rooms.py` → `end_room_session()` | Only runs for `peer_1on1` and `public_room` modes |
| Roleplay eval missing | `services/roleplay_service.py` → `evaluate_session()` | Runs as background task after end-session; check logs |
| Rate limited | `core/middleware.py` → `RateLimitMiddleware` | Default: 100 req/min per IP |
| DB connection error | `core/database.py` | Check `DATABASE_URL` in `.env` |
| CORS blocked | `main.py` → CORSMiddleware | Add your origin to `CORS_ORIGINS` |

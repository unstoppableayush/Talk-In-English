# Speaking App — AI-Powered Communication Platform

An AI-powered speaking/language practice application with multi-provider LLM support, real-time WebSocket chat, speech processing, and comprehensive evaluation scoring.

> **Detailed docs:** [backend/README.md](backend/README.md) · [frontend/README.md](frontend/README.md)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.12, async |
| Frontend | React 18, TypeScript 5.6, Vite 6, Tailwind CSS 3.4 |
| Database | PostgreSQL 16 (4 schemas, UUID PKs, JSONB) |
| Cache / Pub/Sub | Redis 7 |
| LLM Providers | OpenAI (gpt-4o), Grok (grok-3-latest), Gemini (gemini-2.0-flash), DeepSeek (deepseek-chat) — auto-fallback |
| Speech-to-Text | Deepgram Nova-2 (real-time WebSocket) |
| Text-to-Speech | ElevenLabs (multilingual v2), OpenAI TTS (tts-1) — auto-fallback |
| State | Zustand 5, TanStack Query 5 |
| Deployment | Docker multi-stage, nginx, docker-compose (dev + prod) |

---

## Project Structure

```
speaking-app/
├── backend/                    → Python FastAPI   (see backend/README.md)
│   ├── app/
│   │   ├── core/               Config, security, DB engine, deps
│   │   ├── models/             10 SQLAlchemy models
│   │   ├── schemas/            10 Pydantic schema files
│   │   ├── api/                8 REST routers
│   │   ├── ws/                 3 WebSocket handlers + ConnectionManager
│   │   ├── services/           AI, speech, roleplay services
│   │   └── workers/            Background tasks
│   ├── migrations/             Alembic + init.sql
│   └── requirements.txt
│
├── frontend/                   → React + Vite     (see frontend/README.md)
│   ├── src/
│   │   ├── pages/              10 page components
│   │   ├── layouts/            AppLayout + AuthLayout
│   │   ├── hooks/              useSessionSocket
│   │   ├── stores/             authStore, roomStore (Zustand)
│   │   ├── lib/                api.ts (Axios), ws.ts (WebSocket)
│   │   └── types/              All TypeScript interfaces
│   └── package.json
│
├── nginx/                      nginx.conf for reverse proxy
├── docker-compose.yml          Development (hot-reload)
├── docker-compose.prod.yml     Production (replicas, limits)
├── .env.example                All environment variables
└── README.md                   ← You are here
```

---

## What Was Built — Phase by Phase

### Phase 1 — Architecture & Design
- Architecture docs in `docs/architecture/` (high-level, microservices, DB schema, API, WS events, scalability)

### Phase 2 — Database & Models
- PostgreSQL schemas: `auth`, `sessions`, `eval`, `ai`
- SQLAlchemy 2.0 async models: User, Session, Message, Evaluation, AIFeedback, AIInteraction, LeaderboardEntry
- Alembic + `init.sql` seed script

### Phase 3 — Auth & Core API
- JWT auth (access 15min + refresh 7d), bcrypt hashing, HTTPBearer
- RBAC with `require_role()` dependency
- Middleware: RequestID, SecurityHeaders, RequestLogging, RateLimit (100/min), CORS
- REST endpoints: `POST /register`, `POST /login`, `POST /refresh`, `GET /me`

### Phase 4 — Sessions & Rooms
- Room CRUD: create, list, get, join/leave
- Session lifecycle: create, end, manage participants
- Room types: `public`, `private`, `one_on_one`
- Session modes: `public_room`, `peer_1on1`, `ai_1on1`

### Phase 5 — WebSocket Real-Time
- ConnectionManager with Redis pub/sub for scaling
- Chat handler: `chat.message`, `session.user_joined`, `session.user_left`
- Audio handler: Deepgram STT streaming, real-time transcription

### Phase 6 — Full Frontend
- 10 pages: Login, Register, Dashboard, AI Chat, Peer Chat, Public Room, Score Report, Admin Panel, Roleplay
- Zustand stores (auth + room), Axios interceptors with token refresh
- WebSocket hook (`useSessionSocket`)
- Tailwind UI with custom primary palette

### Phase 7 — AI Services + Silent Monitoring
- ConversationManager (context window, system prompts per mode)
- ModerationService (toxicity + off-topic detection)
- ScoringEngine (8-dimension evaluation: fluency, grammar, vocabulary, pronunciation, coherence, confidence, engagement, listening)
- Auto-trigger scoring on session end

### Phase 8 — Section Testing
- `POST /section-tests/generate` → AI-generated test questions
- `POST /section-tests/{id}/submit` → AI grading with detailed feedback
- Model: `SectionTest` with content (JSONB), score, feedback (JSONB)

### Phase 9 — Leaderboard & Weakness Analysis
- `GET /leaderboard` → ranked by XP with period filtering (weekly/monthly/all-time)
- `GET /progress/weakness-analysis` → AI-powered weakness identification with practice suggestions
- `GET /progress/dashboard` → XP, streak, session stats, dimension averages

### Phase 10 — Docker & Production
- Multi-stage Dockerfiles (backend + frontend)
- `docker-compose.yml` — dev with hot-reload
- `docker-compose.prod.yml` — production with resource limits, replicas, health checks
- nginx reverse proxy: `/api/` → backend, `/ws/` → backend WebSocket, `/` → frontend SPA

### Phase 11 — AI Roleplay Module
- Scenario catalog: `GET /roleplay/scenarios`, `POST /roleplay/seed` (seed predefined)
- Session management: start, get, list, report endpoints
- WebSocket: `ws/roleplay/{session_id}` (send/receive messages, end session)
- RoleplayEngine: context-aware AI replies, 7-dimension evaluation
- Frontend: RolePlayPage with setup → conversation → report flow

### Multi-Provider LLM System (Post Phase 11)
- `FallbackLLMProvider` chains providers in order (configurable via `LLM_PROVIDER_ORDER`)
- Providers: OpenAI, Grok, Gemini, DeepSeek — skips any with missing API keys
- Auto-retries on failure, falls through to next provider

### ElevenLabs TTS (Post Phase 11)
- `FallbackTTS` chains ElevenLabs → OpenAI TTS
- Configurable via `TTS_PROVIDER_ORDER`

---

## Quick Start

### 1. Environment Variables

```bash
cp .env.example .env
# Fill in at minimum:
#   POSTGRES_PASSWORD, JWT_SECRET
#   At least one LLM key (OPENAI_API_KEY recommended)
#   DEEPGRAM_API_KEY (for STT)
```

### 2. Docker (Recommended)

```bash
docker-compose up -d
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
# API docs: http://localhost:8000/docs
```

### 3. Manual

```bash
# Start Postgres + Redis first

# Backend
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### 4. Production

```bash
docker-compose -f docker-compose.prod.yml up -d
# App served via nginx on port 80
```

---

## Conversation Modes

| Mode | Description | AI Role |
|------|-------------|---------|
| AI 1-on-1 | User talks with AI partner | Active conversationalist |
| Peer Monitored | Two users talk, AI watches silently | Silent observer, scores both |
| Public Room | Up to 5 speakers + unlimited listeners | Moderator (topic, turns) |
| AI Roleplay | User plays a scenario with AI character | Role-play partner + evaluator |

---

## Evaluation Dimensions

Each session scores users on 8 dimensions (0–100):

| Dimension | What It Measures |
|-----------|-----------------|
| Fluency | Speech flow, hesitation, filler words |
| Grammar | Sentence structure, tense, agreement |
| Vocabulary | Word range, precision, sophistication |
| Pronunciation | Phoneme accuracy, stress patterns |
| Coherence | Logical flow, topic maintenance |
| Confidence | Assertiveness, pace, delivery |
| Engagement | Active participation, questions asked |
| Listening | Response relevance, follow-up quality |

---

## Key Files Reference

| What | File |
|------|------|
| All env vars | `.env.example` |
| Backend entry | `backend/app/main.py` |
| All config | `backend/app/core/config.py` |
| LLM providers | `backend/app/services/ai_service.py` |
| TTS/STT | `backend/app/services/speech_service.py` |
| Roleplay engine | `backend/app/services/roleplay_service.py` |
| Frontend entry | `frontend/src/main.tsx` |
| All routes | `frontend/src/App.tsx` |
| API client | `frontend/src/lib/api.ts` |
| Auth state | `frontend/src/stores/authStore.ts` |
| All TS types | `frontend/src/types/index.ts` |
| Docker dev | `docker-compose.yml` |
| Docker prod | `docker-compose.prod.yml` |
| nginx | `nginx/nginx.conf` |

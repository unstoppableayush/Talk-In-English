-- ============================================================
-- Speaking App – Full Schema DDL (PostgreSQL 16+)
-- Generated from SQLAlchemy models
-- Run once against a fresh database or use Alembic for diffs.
-- ============================================================

-- ── Schemas ─────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS sessions;
CREATE SCHEMA IF NOT EXISTS eval;
CREATE SCHEMA IF NOT EXISTS ai;

-- ── Extensions ──────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()


-- ============================================================
-- 1. auth.users
-- ============================================================
CREATE TABLE auth.users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255)  NOT NULL UNIQUE,
    username        VARCHAR(100)  NOT NULL UNIQUE,
    hashed_password TEXT,
    google_id       VARCHAR(255)  UNIQUE,
    full_name       VARCHAR(200),
    avatar_url      VARCHAR(500),
    native_language VARCHAR(10)   DEFAULT 'en',
    target_language VARCHAR(10)   DEFAULT 'en',
    xp              INTEGER       NOT NULL DEFAULT 0,
    streak_days     INTEGER       NOT NULL DEFAULT 0,
    is_active       BOOLEAN       NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);


-- ============================================================
-- 2. sessions.rooms
-- ============================================================
CREATE TABLE sessions.rooms (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(200)  NOT NULL,
    topic           TEXT,
    description     TEXT,
    language        VARCHAR(10)   NOT NULL DEFAULT 'en',
    max_speakers    INTEGER       NOT NULL DEFAULT 5,
    created_by      UUID          NOT NULL REFERENCES auth.users(id),
    is_active       BOOLEAN       NOT NULL DEFAULT TRUE,
    config          JSONB         NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX idx_rooms_active ON sessions.rooms (is_active) WHERE is_active = true;


-- ============================================================
-- 3. sessions.sessions
-- ============================================================
CREATE TABLE sessions.sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id         UUID          REFERENCES sessions.rooms(id),
    mode            VARCHAR(20)   NOT NULL,   -- ai_1on1, peer_1on1, public_room
    status          VARCHAR(20)   NOT NULL DEFAULT 'waiting',  -- waiting, active, completed, cancelled
    created_by      UUID          NOT NULL REFERENCES auth.users(id),
    language        VARCHAR(10)   NOT NULL DEFAULT 'en',
    topic           TEXT,
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    duration_sec    INTEGER,
    config          JSONB         NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_status     ON sessions.sessions (status);
CREATE INDEX idx_sessions_mode       ON sessions.sessions (mode);
CREATE INDEX idx_sessions_created_at ON sessions.sessions (created_at);


-- ============================================================
-- 4. sessions.room_participants
-- ============================================================
CREATE TABLE sessions.room_participants (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id            UUID          NOT NULL REFERENCES sessions.sessions(id) ON DELETE CASCADE,
    user_id               UUID          NOT NULL REFERENCES auth.users(id),
    role                  VARCHAR(20)   NOT NULL DEFAULT 'speaker',  -- speaker | listener
    joined_at             TIMESTAMPTZ   NOT NULL DEFAULT now(),
    left_at               TIMESTAMPTZ,
    is_active             BOOLEAN       NOT NULL DEFAULT TRUE,
    speaking_duration_sec INTEGER       NOT NULL DEFAULT 0,

    CONSTRAINT uq_room_participant UNIQUE (session_id, user_id)
);

CREATE INDEX idx_rp_session_active ON sessions.room_participants (session_id, is_active);
CREATE INDEX idx_rp_user           ON sessions.room_participants (user_id);


-- ============================================================
-- 5. sessions.messages
-- ============================================================
CREATE TABLE sessions.messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID          NOT NULL REFERENCES sessions.sessions(id) ON DELETE CASCADE,
    sender_id       UUID          REFERENCES auth.users(id),
    sender_type     VARCHAR(20)   NOT NULL,   -- user, ai, system, moderator
    content         TEXT          NOT NULL,
    message_type    VARCHAR(20)   NOT NULL DEFAULT 'text',  -- text, audio, mixed
    sequence_no     INTEGER       NOT NULL DEFAULT 0,
    audio_url       VARCHAR(500),
    audio_duration_ms INTEGER,
    stt_confidence  FLOAT,
    word_count      INTEGER,
    metadata        JSONB         NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX idx_msg_session_seq     ON sessions.messages (session_id, sequence_no);
CREATE INDEX idx_msg_session_created ON sessions.messages (session_id, created_at);
CREATE INDEX idx_msg_sender          ON sessions.messages (sender_id);


-- ============================================================
-- 6. eval.session_scores
-- ============================================================
CREATE TABLE eval.session_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID          NOT NULL REFERENCES sessions.sessions(id) ON DELETE CASCADE,
    user_id         UUID          NOT NULL REFERENCES auth.users(id),

    -- Skill dimensions (0-100)
    fluency         INTEGER       NOT NULL DEFAULT 0,
    clarity         INTEGER       NOT NULL DEFAULT 0,
    grammar         INTEGER       NOT NULL DEFAULT 0,
    vocabulary      INTEGER       NOT NULL DEFAULT 0,
    coherence       INTEGER       NOT NULL DEFAULT 0,
    leadership      INTEGER       NOT NULL DEFAULT 0,
    engagement      INTEGER       NOT NULL DEFAULT 0,
    turn_taking     INTEGER       NOT NULL DEFAULT 0,
    overall         INTEGER       NOT NULL DEFAULT 0,

    xp_earned       INTEGER       NOT NULL DEFAULT 0,
    scored_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT uq_session_score   UNIQUE (session_id, user_id),
    CONSTRAINT ck_ss_fluency      CHECK (fluency    BETWEEN 0 AND 100),
    CONSTRAINT ck_ss_clarity      CHECK (clarity    BETWEEN 0 AND 100),
    CONSTRAINT ck_ss_grammar      CHECK (grammar    BETWEEN 0 AND 100),
    CONSTRAINT ck_ss_vocabulary   CHECK (vocabulary BETWEEN 0 AND 100),
    CONSTRAINT ck_ss_coherence    CHECK (coherence  BETWEEN 0 AND 100),
    CONSTRAINT ck_ss_leadership   CHECK (leadership BETWEEN 0 AND 100),
    CONSTRAINT ck_ss_engagement   CHECK (engagement BETWEEN 0 AND 100),
    CONSTRAINT ck_ss_turn_taking  CHECK (turn_taking BETWEEN 0 AND 100),
    CONSTRAINT ck_ss_overall      CHECK (overall    BETWEEN 0 AND 100)
);

CREATE INDEX idx_ss_user_created ON eval.session_scores (user_id, scored_at);


-- ============================================================
-- 7. eval.progress_snapshots
-- ============================================================
CREATE TABLE eval.progress_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID          NOT NULL REFERENCES auth.users(id),
    snapshot_date       DATE          NOT NULL,
    period              VARCHAR(10)   NOT NULL,   -- 7d, 30d, all

    fluency_avg         FLOAT,
    clarity_avg         FLOAT,
    grammar_avg         FLOAT,
    vocabulary_avg      FLOAT,
    coherence_avg       FLOAT,
    leadership_avg      FLOAT,
    engagement_avg      FLOAT,
    turn_taking_avg     FLOAT,
    overall_avg         FLOAT,

    sessions_count      INTEGER       NOT NULL DEFAULT 0,
    total_duration_sec  INTEGER       NOT NULL DEFAULT 0,
    total_xp            INTEGER       NOT NULL DEFAULT 0,
    metadata            JSONB         NOT NULL DEFAULT '{}',

    CONSTRAINT uq_progress_snapshot UNIQUE (user_id, snapshot_date, period)
);

CREATE INDEX idx_ps_user_period ON eval.progress_snapshots (user_id, period, snapshot_date);


-- ============================================================
-- 8. eval.section_tests
-- ============================================================
CREATE TABLE eval.section_tests (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title             VARCHAR(300)  NOT NULL,
    description       TEXT,
    section           VARCHAR(20)   NOT NULL,   -- speaking, listening, writing, reading
    difficulty_level  VARCHAR(20)   NOT NULL DEFAULT 'intermediate',
    language          VARCHAR(10)   NOT NULL DEFAULT 'en',
    time_limit_sec    INTEGER,
    pass_threshold    INTEGER       NOT NULL DEFAULT 60,
    questions         JSONB         NOT NULL DEFAULT '[]',
    is_active         BOOLEAN       NOT NULL DEFAULT TRUE,
    created_by        UUID          REFERENCES auth.users(id),
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX idx_st_section_level ON eval.section_tests (section, difficulty_level);


-- ============================================================
-- 9. eval.test_attempts
-- ============================================================
CREATE TABLE eval.test_attempts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id         UUID          NOT NULL REFERENCES eval.section_tests(id) ON DELETE CASCADE,
    user_id         UUID          NOT NULL REFERENCES auth.users(id),
    answers         JSONB         NOT NULL DEFAULT '[]',
    score           FLOAT,
    passed          BOOLEAN,
    question_scores JSONB         NOT NULL DEFAULT '[]',
    xp_earned       INTEGER       NOT NULL DEFAULT 0,
    started_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    duration_sec    INTEGER,

    CONSTRAINT ck_ta_score CHECK (score BETWEEN 0 AND 100)
);

CREATE INDEX idx_ta_user_test  ON eval.test_attempts (user_id, test_id);
CREATE INDEX idx_ta_completed  ON eval.test_attempts (completed_at);


-- ============================================================
-- 10. eval.leaderboard_entries
-- ============================================================
CREATE TABLE eval.leaderboard_entries (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID          NOT NULL REFERENCES auth.users(id),
    period            VARCHAR(10)   NOT NULL,   -- weekly, monthly, alltime
    period_start      DATE          NOT NULL,
    rank              INTEGER       NOT NULL,
    total_xp          INTEGER       NOT NULL DEFAULT 0,
    sessions_count    INTEGER       NOT NULL DEFAULT 0,
    avg_overall_score INTEGER       NOT NULL DEFAULT 0,
    computed_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT uq_leaderboard_entry UNIQUE (user_id, period, period_start),
    CONSTRAINT ck_lb_rank           CHECK (rank >= 1),
    CONSTRAINT ck_lb_xp             CHECK (total_xp >= 0)
);

CREATE INDEX idx_lb_period_rank ON eval.leaderboard_entries (period, period_start, rank);
CREATE INDEX idx_lb_user        ON eval.leaderboard_entries (user_id);


-- ============================================================
-- 11. ai.ai_feedback_reports
-- ============================================================
CREATE TABLE ai.ai_feedback_reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID          NOT NULL REFERENCES sessions.sessions(id) ON DELETE CASCADE,
    user_id             UUID          NOT NULL REFERENCES auth.users(id),
    dimension_feedback  JSONB         NOT NULL DEFAULT '{}',
    strengths           JSONB         NOT NULL DEFAULT '[]',
    improvement_areas   JSONB         NOT NULL DEFAULT '[]',
    suggested_exercises JSONB         NOT NULL DEFAULT '[]',
    summary             TEXT,
    raw_response        JSONB         NOT NULL DEFAULT '{}',
    model_used          VARCHAR(50)   NOT NULL DEFAULT 'gpt-4o',
    prompt_version      VARCHAR(20)   NOT NULL DEFAULT 'v1',
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX idx_afr_user    ON ai.ai_feedback_reports (user_id);
CREATE INDEX idx_afr_session ON ai.ai_feedback_reports (session_id);
CREATE INDEX idx_afr_created ON ai.ai_feedback_reports (created_at);


-- ============================================================
-- 12. ai.ai_interactions (already existed — included for completeness)
-- ============================================================
CREATE TABLE IF NOT EXISTS ai.ai_interactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID          NOT NULL REFERENCES sessions.sessions(id) ON DELETE CASCADE,
    user_id         UUID          REFERENCES auth.users(id),
    interaction_type VARCHAR(30)  NOT NULL,
    prompt          TEXT          NOT NULL,
    response        TEXT,
    model_used      VARCHAR(50)  NOT NULL,
    tokens_used     INTEGER      NOT NULL DEFAULT 0,
    latency_ms      INTEGER,
    metadata        JSONB         NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

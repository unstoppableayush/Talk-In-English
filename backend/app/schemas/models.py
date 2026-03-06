import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


# --- Auth Schemas ---

class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    credential: str  # Google ID token from GSI


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    native_language: str | None = None
    target_language: str | None = None
    xp: int = 0
    streak_days: int = 0
    avatar_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class UserUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=2, max_length=100)
    avatar_url: str | None = Field(None, max_length=500)
    native_language: str | None = Field(None, max_length=10)
    target_language: str | None = Field(None, max_length=10)


# --- Session Schemas ---

class SessionConfig(BaseModel):
    language: str = "en"
    topic: str | None = None
    difficulty: str = "intermediate"


class CreateSessionRequest(BaseModel):
    mode: str = Field(pattern=r"^(ai_1on1|peer_1on1|public_room)$")
    config: SessionConfig = SessionConfig()


class SessionResponse(BaseModel):
    id: uuid.UUID
    mode: str
    status: str
    language: str = "en"
    topic: str | None = None
    config: dict
    created_by: uuid.UUID
    room_id: uuid.UUID | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_sec: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class JoinSessionRequest(BaseModel):
    role: str = Field(default="speaker", pattern=r"^(speaker|listener)$")


class ParticipantResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    hand_raised: bool = False
    speaking_duration_sec: int = 0
    joined_at: datetime

    model_config = {"from_attributes": True}


class PromoteRequest(BaseModel):
    """Used by session owner / moderator to promote a listener to speaker."""
    user_id: uuid.UUID


class RaiseHandResponse(BaseModel):
    user_id: uuid.UUID
    hand_raised: bool


# --- Room Schemas ---

class RoomConfig(BaseModel):
    language: str = "en"
    difficulty: str = "intermediate"
    ai_moderation_level: str = "standard"


class CreateRoomRequest(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    room_type: str = Field(default="public", pattern=r"^(public|private|one_on_one)$")
    topic: str | None = None
    description: str | None = None
    language: str = "en"
    max_speakers: int = Field(default=5, ge=2, le=5)
    config: RoomConfig = RoomConfig()


class RoomResponse(BaseModel):
    id: uuid.UUID
    name: str
    room_type: str
    topic: str | None
    description: str | None
    language: str
    max_speakers: int
    is_active: bool
    speaker_count: int = 0
    listener_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Session Score Schemas ---

class SessionScoreResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    user_id: uuid.UUID
    fluency: int
    clarity: int
    grammar: int
    vocabulary: int
    coherence: int
    leadership: int
    engagement: int
    turn_taking: int
    overall: int
    xp_earned: int
    scored_at: datetime

    model_config = {"from_attributes": True}


# --- AI Feedback Schemas ---

class AIFeedbackResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    user_id: uuid.UUID
    dimension_feedback: dict
    strengths: list
    improvement_areas: list
    suggested_exercises: list
    summary: str | None
    model_used: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Section Test Schemas ---

class CreateSectionTestRequest(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    description: str | None = None
    section: str = Field(pattern=r"^(speaking|listening|writing|reading)$")
    difficulty_level: str = Field(default="intermediate", pattern=r"^(beginner|intermediate|advanced)$")
    language: str = "en"
    time_limit_sec: int | None = None
    pass_threshold: int = Field(default=60, ge=0, le=100)
    questions: list[dict] = []


class SectionTestResponse(BaseModel):
    id: uuid.UUID
    title: str
    section: str
    difficulty_level: str
    language: str
    time_limit_sec: int | None
    pass_threshold: int
    question_count: int = 0
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SubmitTestAttemptRequest(BaseModel):
    test_id: uuid.UUID
    answers: list[dict]


class TestAttemptResponse(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    user_id: uuid.UUID
    score: float | None
    passed: bool | None
    question_scores: list[dict] = []
    xp_earned: int
    started_at: datetime
    completed_at: datetime | None
    duration_sec: int | None

    model_config = {"from_attributes": True}


# --- Leaderboard Schemas ---

class LeaderboardEntryResponse(BaseModel):
    rank: int
    user_id: uuid.UUID
    username: str | None = None
    avatar_url: str | None = None
    total_xp: int
    sessions_count: int
    avg_overall_score: int

    model_config = {"from_attributes": True}


class LeaderboardResponse(BaseModel):
    period: str
    period_start: date
    entries: list[LeaderboardEntryResponse]


# --- Progress Schemas ---

class DimensionAvg(BaseModel):
    fluency: float | None = None
    clarity: float | None = None
    grammar: float | None = None
    vocabulary: float | None = None
    coherence: float | None = None
    leadership: float | None = None
    engagement: float | None = None
    turn_taking: float | None = None
    overall: float | None = None


class DashboardResponse(BaseModel):
    xp: int
    streak_days: int
    recent_sessions: int
    total_sessions: int
    total_practice_minutes: int
    snapshots: dict[str, DimensionAvg]  # keyed by period: "7d", "30d", "all"


# --- Message / Transcript ---

class MessageResponse(BaseModel):
    id: uuid.UUID
    sender_type: str
    sender_name: str | None = None
    content: str
    message_type: str
    sequence_no: int = 0
    word_count: int | None = None
    stt_confidence: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TranscriptResponse(BaseModel):
    session_id: uuid.UUID
    mode: str
    duration_sec: int | None
    messages: list[MessageResponse]


# --- Generic ---

class ApiResponse(BaseModel):
    status: str = "ok"
    data: dict | list | None = None


class ErrorResponse(BaseModel):
    status: str = "error"
    error: dict


# --- Roleplay Schemas ---

class RoleplayScenarioResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    category: str
    ai_role: str
    user_role: str
    difficulty: str
    language: str
    starting_prompt: str
    expected_topics: list[str] = []
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StartRoleplayRequest(BaseModel):
    scenario_id: uuid.UUID | None = None
    custom_topic: str | None = None
    difficulty: str = Field(default="intermediate", pattern=r"^(beginner|intermediate|advanced)$")
    language: str = "en"


class RoleplaySessionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    scenario_id: uuid.UUID | None
    custom_topic: str | None
    difficulty: str
    language: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    duration_sec: int | None

    model_config = {"from_attributes": True}


class RoleplayMessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    sender: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SendRoleplayMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class RoleplayEvaluationResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    user_id: uuid.UUID
    fluency_score: int
    grammar_score: int
    vocabulary_score: int
    confidence_score: int
    clarity_score: int
    relevance_score: int
    consistency_score: int
    overall_score: float
    xp_earned: int
    strengths: list[str] = []
    weaknesses: list[str] = []
    improvement_suggestions: list[str] = []
    filler_words: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}


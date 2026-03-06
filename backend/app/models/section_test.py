import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base, TimestampMixin


class SectionTest(TimestampMixin, Base):
    """
    A reusable test definition for a specific skill section.
    Admins / content creators populate these. Users take attempts against them.
    """
    __tablename__ = "section_tests"
    __table_args__ = (
        Index("idx_st_section_level", "section", "difficulty_level"),
        {"schema": "eval"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    section: Mapped[str] = mapped_column(String(20), nullable=False)
    # section: speaking | listening | writing | reading
    difficulty_level: Mapped[str] = mapped_column(String(20), nullable=False, default="intermediate")
    # difficulty_level: beginner | intermediate | advanced
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    time_limit_sec: Mapped[int | None] = mapped_column(Integer)
    pass_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    # Ordered list of question objects:
    # [{"id": "q1", "type": "audio_prompt", "prompt": "...", "rubric": "..."}]
    questions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"))


class TestAttempt(Base):
    """
    One user's single attempt at a SectionTest.
    Stores both the user's answers and the AI-graded scores.
    """
    __tablename__ = "test_attempts"
    __table_args__ = (
        Index("idx_ta_user_test", "user_id", "test_id"),
        Index("idx_ta_completed", "completed_at"),
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_ta_score"),
        {"schema": "eval"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval.section_tests.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"), nullable=False)

    # Ordered list matching questions: [{"question_id": "q1", "answer": "...", "audio_url": "..."}]
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)

    score: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    # Per-question breakdown: [{"question_id":"q1","score":85,"feedback":"..."}]
    question_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_sec: Mapped[int | None] = mapped_column(Integer)

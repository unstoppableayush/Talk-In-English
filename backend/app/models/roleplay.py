"""
Roleplay models — scenario definitions, sessions, messages, evaluations.
"""

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.user import Base, TimestampMixin


class RoleplayScenario(TimestampMixin, Base):
    """Pre-defined roleplay scenario template."""

    __tablename__ = "roleplay_scenarios"
    __table_args__ = (
        Index("idx_rps_category", "category"),
        Index("idx_rps_difficulty", "difficulty"),
        {"schema": "ai"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    # category examples: interview, customer_support, business, casual, academic, debate
    ai_role: Mapped[str] = mapped_column(String(200), nullable=False)
    user_role: Mapped[str] = mapped_column(String(200), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="intermediate")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    starting_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected_topics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("public.app_users.id"))


class RoleplaySession(TimestampMixin, Base):
    """A single user's roleplay conversation session."""

    __tablename__ = "roleplay_sessions"
    __table_args__ = (
        Index("idx_rpses_user", "user_id"),
        Index("idx_rpses_status", "status"),
        {"schema": "ai"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.app_users.id"), nullable=False
    )
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai.roleplay_scenarios.id")
    )
    custom_topic: Mapped[str | None] = mapped_column(String(500))
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="intermediate")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # status: active | completed | cancelled
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_sec: Mapped[int | None] = mapped_column(Integer)

    messages: Mapped[list["RoleplayMessage"]] = relationship(
        back_populates="session", order_by="RoleplayMessage.created_at"
    )


class RoleplayMessage(Base):
    """Individual message in a roleplay conversation."""

    __tablename__ = "roleplay_messages"
    __table_args__ = (
        Index("idx_rpm_session", "session_id", "created_at"),
        {"schema": "ai"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai.roleplay_sessions.id", ondelete="CASCADE"), nullable=False
    )
    sender: Mapped[str] = mapped_column(String(10), nullable=False)
    # sender: "user" | "ai"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    session: Mapped["RoleplaySession"] = relationship(back_populates="messages")


class RoleplayEvaluation(TimestampMixin, Base):
    """AI-generated end-of-session evaluation for a roleplay session."""

    __tablename__ = "roleplay_evaluations"
    __table_args__ = (
        Index("idx_rpeval_session", "session_id"),
        Index("idx_rpeval_user", "user_id"),
        CheckConstraint("overall_score BETWEEN 0 AND 100", name="ck_rpeval_overall"),
        {"schema": "ai"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai.roleplay_sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.app_users.id"), nullable=False
    )
    fluency_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grammar_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vocabulary_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clarity_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consistency_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    strengths: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    weaknesses: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    improvement_suggestions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    filler_words: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # e.g. {"um": 3, "uh": 2, "like": 5}
    raw_response: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    model_used: Mapped[str] = mapped_column(String(50), nullable=False, default="gpt-4o")

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


class SessionScore(Base):
    """
    One row per (session, user) — stores granular skill dimensions scored 0-100.
    Replaces the old Evaluation + SkillScore pair with explicit columns for each dimension,
    making queries, aggregation, and indexing much simpler.
    """
    __tablename__ = "session_scores"
    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_session_score"),
        Index("idx_ss_user_created", "user_id", "scored_at"),
        CheckConstraint("fluency    BETWEEN 0 AND 100", name="ck_ss_fluency"),
        CheckConstraint("clarity    BETWEEN 0 AND 100", name="ck_ss_clarity"),
        CheckConstraint("grammar    BETWEEN 0 AND 100", name="ck_ss_grammar"),
        CheckConstraint("vocabulary BETWEEN 0 AND 100", name="ck_ss_vocabulary"),
        CheckConstraint("coherence  BETWEEN 0 AND 100", name="ck_ss_coherence"),
        CheckConstraint("leadership BETWEEN 0 AND 100", name="ck_ss_leadership"),
        CheckConstraint("engagement BETWEEN 0 AND 100", name="ck_ss_engagement"),
        CheckConstraint("turn_taking BETWEEN 0 AND 100", name="ck_ss_turn_taking"),
        CheckConstraint("overall    BETWEEN 0 AND 100", name="ck_ss_overall"),
        {"schema": "eval"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"), nullable=False)

    # ── Skill dimensions (0-100 each) ──────────────────────────────
    fluency: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clarity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grammar: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vocabulary: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coherence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leadership: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    engagement: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    turn_taking: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Weighted category averages (computed by the AI scorer)
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ProgressSnapshot(Base):
    """
    Daily / weekly / all-time rollup of a user's skill averages.
    Materialized by a Celery beat task so dashboards are fast.
    """
    __tablename__ = "progress_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date", "period", name="uq_progress_snapshot"),
        Index("idx_ps_user_period", "user_id", "period", "snapshot_date"),
        {"schema": "eval"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # 7d, 30d, all

    # Rolling averages by dimension
    fluency_avg: Mapped[float | None] = mapped_column(Float)
    clarity_avg: Mapped[float | None] = mapped_column(Float)
    grammar_avg: Mapped[float | None] = mapped_column(Float)
    vocabulary_avg: Mapped[float | None] = mapped_column(Float)
    coherence_avg: Mapped[float | None] = mapped_column(Float)
    leadership_avg: Mapped[float | None] = mapped_column(Float)
    engagement_avg: Mapped[float | None] = mapped_column(Float)
    turn_taking_avg: Mapped[float | None] = mapped_column(Float)
    overall_avg: Mapped[float | None] = mapped_column(Float)

    sessions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

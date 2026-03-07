import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


class LeaderboardEntry(Base):
    """
    Pre-computed leaderboard row for a given time window.
    Regenerated periodically by a Celery beat task:
      - 'weekly'  → recomputed every hour, covers Mon-Sun
      - 'monthly' → recomputed every 6 hours
      - 'alltime' → recomputed daily

    Querying is a simple ORDER BY rank for a given (period, period_start).
    """
    __tablename__ = "leaderboard_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "period", "period_start", name="uq_leaderboard_entry"),
        Index("idx_lb_period_rank", "period", "period_start", "rank"),
        Index("idx_lb_user", "user_id"),
        CheckConstraint("rank >= 1", name="ck_lb_rank"),
        CheckConstraint("total_xp >= 0", name="ck_lb_xp"),
        {"schema": "eval"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("public.app_users.id"), nullable=False)

    period: Mapped[str] = mapped_column(String(10), nullable=False)
    # period: weekly | monthly | alltime
    period_start: Mapped[date] = mapped_column(Date, nullable=False)

    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    total_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sessions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_overall_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

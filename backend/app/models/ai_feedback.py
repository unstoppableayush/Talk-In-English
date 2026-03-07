import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


class AIFeedbackReport(Base):
    """
    Rich AI-generated feedback linked to a specific session + user.
    Created asynchronously by the evaluation worker after a session ends.
    The structured JSONB fields allow the frontend to render cards/charts
    while the plain-text summary is good for notifications / email digests.
    """
    __tablename__ = "ai_feedback_reports"
    __table_args__ = (
        Index("idx_afr_user", "user_id"),
        Index("idx_afr_session", "session_id"),
        Index("idx_afr_created", "created_at"),
        {"schema": "ai"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("public.app_users.id"), nullable=False)

    # ── Structured feedback ────────────────────────────────────────
    # Per-dimension textual analysis keyed by dimension name
    # e.g. {"fluency": "Good pace but ...", "grammar": "Watch out for ..."}
    dimension_feedback: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Lists of short bullet strings
    strengths: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    improvement_areas: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    suggested_exercises: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)

    # Free-form summary paragraph from the LLM
    summary: Mapped[str | None] = mapped_column(Text)

    # Full raw LLM response for auditing / reprocessing
    raw_response: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    model_used: Mapped[str] = mapped_column(String(50), nullable=False, default="gpt-4o")
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

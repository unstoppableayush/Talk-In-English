import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


class Message(Base):
    """
    Every spoken / typed / AI-generated message in a session.
    The ordered transcript is rebuilt via (session_id, sequence_no).
    """
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_msg_session_seq", "session_id", "sequence_no"),
        Index("idx_msg_session_created", "session_id", "created_at"),
        Index("idx_msg_sender", "sender_id"),
        {"schema": "sessions"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.sessions.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"))
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False)  # user, ai, system, moderator
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")  # text, audio, mixed
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    audio_url: Mapped[str | None] = mapped_column(String(500))
    audio_duration_ms: Mapped[int | None] = mapped_column(Integer)
    stt_confidence: Mapped[float | None] = mapped_column(Float)
    word_count: Mapped[int | None] = mapped_column(Integer)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

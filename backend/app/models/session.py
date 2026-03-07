import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base, TimestampMixin


class Room(TimestampMixin, Base):
    """
    Persistent room container.
    A room can host many sessions over time (each session is one live conversation).
    """
    __tablename__ = "rooms"
    __table_args__ = (
        Index("idx_rooms_active", "is_active", postgresql_where="is_active = true"),
        {"schema": "sessions"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    room_type: Mapped[str] = mapped_column(String(20), nullable=False, default="public")
    # room_type: public | private | one_on_one
    topic: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    max_speakers: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("public.app_users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Session(Base):
    """
    One live conversation instance.
    Belongs to a Room (for public_room mode) or stands alone (ai_1on1, peer_1on1).
    """
    __tablename__ = "sessions"
    __table_args__ = (
        Index("idx_sessions_status", "status"),
        Index("idx_sessions_mode", "mode"),
        Index("idx_sessions_created_at", "created_at"),
        {"schema": "sessions"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.rooms.id"))
    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # ai_1on1, peer_1on1, public_room
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="waiting")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("public.app_users.id"), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    topic: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class RoomParticipant(Base):
    """
    Tracks who is in a session and whether they are a speaker or listener.
    Listeners in public rooms ARE stored here for the join/leave audit trail,
    but they are NOT evaluated or scored (the eval pipeline skips listener roles).
    """
    __tablename__ = "room_participants"
    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_room_participant"),
        Index("idx_rp_session_active", "session_id", "is_active"),
        Index("idx_rp_user", "user_id"),
        {"schema": "sessions"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("public.app_users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="speaker")
    # role: speaker | listener
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    hand_raised: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # speaking_duration_sec accumulated while role=speaker
    speaking_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

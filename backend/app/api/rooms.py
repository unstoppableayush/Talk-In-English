from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.session import Room, Session, RoomParticipant
from app.models.user import User
from app.schemas.models import (
    CreateRoomRequest,
    CreateSessionRequest,
    JoinSessionRequest,
    ParticipantResponse,
    PromoteRequest,
    RaiseHandResponse,
    RoomResponse,
    SessionResponse,
)
from app.services.ai_service import scoring_engine

router = APIRouter()


# ── Room CRUD ──────────────────────────────────────────────────

@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    body: CreateRoomRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new room (public, private, or 1-on-1)."""
    room = Room(
        name=body.name,
        room_type=body.room_type,
        topic=body.topic,
        description=body.description,
        language=body.language,
        max_speakers=2 if body.room_type == "one_on_one" else body.max_speakers,
        created_by=user.id,
        config=body.config.model_dump(),
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return RoomResponse.model_validate(room)


@router.get("", response_model=list[RoomResponse])
async def list_rooms(
    room_type: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List active rooms. Public rooms visible to all; filter by type."""
    query = select(Room).where(Room.is_active.is_(True))
    if room_type:
        query = query.where(Room.room_type == room_type)
    query = query.order_by(Room.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    rooms = result.scalars().all()
    return [RoomResponse.model_validate(r) for r in rooms]


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Room).where(Room.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return RoomResponse.model_validate(room)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_room(
    room_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Room).where(Room.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    if room.created_by != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only room owner or admin can delete")
    room.is_active = False
    await db.commit()


# ── Join / Leave Room (via Session) ────────────────────────────

@router.post("/{room_id}/join", response_model=ParticipantResponse)
async def join_room(
    room_id: str,
    body: JoinSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join the active session for this room (or create one)."""
    result = await db.execute(select(Room).where(Room.id == room_id, Room.is_active.is_(True)))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    # Find or create an active session for this room
    session_result = await db.execute(
        select(Session).where(
            Session.room_id == room.id,
            Session.status.in_(("waiting", "active")),
        ).order_by(Session.created_at.desc()).limit(1)
    )
    session = session_result.scalar_one_or_none()

    if not session:
        session = Session(
            room_id=room.id,
            mode="public_room" if room.room_type == "public" else (
                "ai_1on1" if room.room_type == "one_on_one" else "peer_1on1"
            ),
            created_by=user.id,
            language=room.language,
            topic=room.topic,
            started_at=datetime.now(timezone.utc),
            status="active",
        )
        db.add(session)
        await db.flush()

    # Check if already joined
    existing = await db.execute(
        select(RoomParticipant).where(
            RoomParticipant.session_id == session.id,
            RoomParticipant.user_id == user.id,
            RoomParticipant.is_active.is_(True),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already in this room")

    # Speaker capacity check
    if body.role == "speaker":
        count_result = await db.execute(
            select(func.count()).where(
                RoomParticipant.session_id == session.id,
                RoomParticipant.role == "speaker",
                RoomParticipant.is_active.is_(True),
            )
        )
        speaker_count = count_result.scalar()
        if speaker_count >= room.max_speakers:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Room is full ({room.max_speakers} speakers max)",
            )

    participant = RoomParticipant(
        session_id=session.id, user_id=user.id, role=body.role,
    )
    db.add(participant)
    await db.commit()
    await db.refresh(participant)
    return ParticipantResponse.model_validate(participant)


@router.post("/{room_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_room(
    room_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Leave the active session for this room."""
    session_result = await db.execute(
        select(Session).where(
            Session.room_id == room_id,
            Session.status.in_(("waiting", "active")),
        ).order_by(Session.created_at.desc()).limit(1)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active session")

    part_result = await db.execute(
        select(RoomParticipant).where(
            RoomParticipant.session_id == session.id,
            RoomParticipant.user_id == user.id,
            RoomParticipant.is_active.is_(True),
        )
    )
    participant = part_result.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in this room")

    participant.is_active = False
    participant.left_at = datetime.now(timezone.utc)
    await db.commit()


# ── End Session ────────────────────────────────────────────────

@router.post("/{room_id}/end", response_model=SessionResponse)
async def end_room_session(
    room_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """End the active session for this room. Only the room creator or admin can end it.
    Automatically triggers AI evaluation for peer_1on1 (silent monitoring) and public_room sessions."""
    room_result = await db.execute(select(Room).where(Room.id == room_id))
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    if room.created_by != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only room owner or admin can end session")

    session_result = await db.execute(
        select(Session).where(
            Session.room_id == room.id,
            Session.status.in_(("waiting", "active")),
        ).order_by(Session.created_at.desc()).limit(1)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active session")

    now = datetime.now(timezone.utc)
    session.status = "completed"
    session.ended_at = now
    if session.started_at:
        session.duration_sec = int((now - session.started_at).total_seconds())

    # Mark all active participants as left
    parts_result = await db.execute(
        select(RoomParticipant).where(
            RoomParticipant.session_id == session.id,
            RoomParticipant.is_active.is_(True),
        )
    )
    for p in parts_result.scalars().all():
        p.is_active = False
        p.left_at = now

    await db.commit()
    await db.refresh(session)

    # Auto-trigger AI evaluation for peer 1-on-1 (silent monitoring) and public rooms
    if session.mode in ("peer_1on1", "public_room"):
        background_tasks.add_task(scoring_engine.evaluate_session, str(session.id))

    return SessionResponse.model_validate(session)


# ── Promote Listener → Speaker ─────────────────────────────────

@router.post("/{room_id}/promote", response_model=ParticipantResponse)
async def promote_to_speaker(
    room_id: str,
    body: PromoteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Promote a listener to speaker. Only room owner, admin, or moderator can promote."""
    room_result = await db.execute(select(Room).where(Room.id == room_id))
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    # Authorization: room owner, admin, or moderator
    if room.created_by != user.id and user.role not in ("admin", "moderator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to promote")

    # Find active session
    session_result = await db.execute(
        select(Session).where(
            Session.room_id == room.id,
            Session.status.in_(("waiting", "active")),
        ).order_by(Session.created_at.desc()).limit(1)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active session")

    # Check speaker capacity
    count_result = await db.execute(
        select(func.count()).where(
            RoomParticipant.session_id == session.id,
            RoomParticipant.role == "speaker",
            RoomParticipant.is_active.is_(True),
        )
    )
    if count_result.scalar() >= room.max_speakers:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="All speaker slots are full")

    # Find the listener to promote
    part_result = await db.execute(
        select(RoomParticipant).where(
            RoomParticipant.session_id == session.id,
            RoomParticipant.user_id == body.user_id,
            RoomParticipant.is_active.is_(True),
        )
    )
    participant = part_result.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User is not an active participant")
    if participant.role == "speaker":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a speaker")

    participant.role = "speaker"
    participant.hand_raised = False
    await db.commit()
    await db.refresh(participant)
    return ParticipantResponse.model_validate(participant)


# ── Raise Hand ─────────────────────────────────────────────────

@router.post("/{room_id}/raise-hand", response_model=RaiseHandResponse)
async def raise_hand(
    room_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle hand-raised state. Listeners can raise hand to request speaker promotion."""
    session_result = await db.execute(
        select(Session).where(
            Session.room_id == room_id,
            Session.status.in_(("waiting", "active")),
        ).order_by(Session.created_at.desc()).limit(1)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active session")

    part_result = await db.execute(
        select(RoomParticipant).where(
            RoomParticipant.session_id == session.id,
            RoomParticipant.user_id == user.id,
            RoomParticipant.is_active.is_(True),
        )
    )
    participant = part_result.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in this room")

    # Toggle hand
    participant.hand_raised = not participant.hand_raised
    await db.commit()

    return RaiseHandResponse(user_id=user.id, hand_raised=participant.hand_raised)


# ── List Participants ──────────────────────────────────────────

@router.get("/{room_id}/participants", response_model=list[ParticipantResponse])
async def list_participants(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List all active participants in the room's current session."""
    session_result = await db.execute(
        select(Session).where(
            Session.room_id == room_id,
            Session.status.in_(("waiting", "active")),
        ).order_by(Session.created_at.desc()).limit(1)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active session")

    parts_result = await db.execute(
        select(RoomParticipant).where(
            RoomParticipant.session_id == session.id,
            RoomParticipant.is_active.is_(True),
        ).order_by(RoomParticipant.joined_at)
    )
    return [ParticipantResponse.model_validate(p) for p in parts_result.scalars().all()]

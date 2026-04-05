import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.message import Message
from app.models.session import Session, RoomParticipant
from app.models.user import User
from app.services.ai_service import scoring_engine
from app.schemas.models import (
    CreateSessionRequest,
    JoinSessionRequest,
    MessageResponse,
    ParticipantResponse,
    SessionResponse,
    TranscriptResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        logger.info("Creating session mode=%s user=%s", body.mode, user.id)
        session = Session(
            mode=body.mode,
            created_by=user.id,
            config=body.config.model_dump(),
        )
        db.add(session)
        await db.flush()

        # Creator joins as speaker automatically
        participant = RoomParticipant(session_id=session.id, user_id=user.id, role="speaker")
        db.add(participant)

        await db.commit()
        await db.refresh(session)
        logger.info("Session created id=%s", session.id)
        return SessionResponse.model_validate(session)
    except Exception as e:
        logger.exception("Error creating session")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    mode: str | None = None,
    session_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        query = (
            select(Session)
            .join(RoomParticipant, RoomParticipant.session_id == Session.id)
            .where(RoomParticipant.user_id == user.id)
        )
        if mode:
            query = query.where(Session.mode == mode)
        if session_status:
            query = query.where(Session.status == session_status)

        query = query.order_by(Session.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(query)
        sessions = result.scalars().all()
        return [SessionResponse.model_validate(s) for s in sessions]
    except Exception as e:
        logger.exception("Error listing sessions for user=%s", user.id)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        return SessionResponse.model_validate(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting session=%s", session_id)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post("/{session_id}/join", response_model=ParticipantResponse)
async def join_session(
    session_id: str,
    body: JoinSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        logger.info("User %s joining session %s as %s", user.id, session_id, body.role)
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if session.status not in ("waiting", "active"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Session not active")

        # Check existing participation
        existing = await db.execute(
            select(RoomParticipant).where(
                RoomParticipant.session_id == session.id,
                RoomParticipant.user_id == user.id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already in session")

        # Check speaker capacity
        if body.role == "speaker":
            count_result = await db.execute(
                select(func.count()).where(
                    RoomParticipant.session_id == session.id,
                    RoomParticipant.role == "speaker",
                    RoomParticipant.is_active.is_(True),
                )
            )
            speaker_count = count_result.scalar()
            if speaker_count >= settings.MAX_SPEAKERS_PER_ROOM:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Room is full")

        participant = RoomParticipant(session_id=session.id, user_id=user.id, role=body.role)
        db.add(participant)
        await db.commit()
        await db.refresh(participant)
        logger.info("User %s joined session %s", user.id, session_id)
        return ParticipantResponse.model_validate(participant)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error joining session=%s", session_id)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post("/{session_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        logger.info("User %s leaving session %s", user.id, session_id)
        result = await db.execute(
            select(RoomParticipant).where(
                RoomParticipant.session_id == session_id,
                RoomParticipant.user_id == user.id,
                RoomParticipant.is_active.is_(True),
            )
        )
        participant = result.scalar_one_or_none()
        if not participant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in session")

        participant.is_active = False
        participant.left_at = datetime.now(timezone.utc)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error leaving session=%s", session_id)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post("/{session_id}/end", response_model=SessionResponse)
async def end_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        logger.info("Ending session %s by user %s", session_id, user.id)
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if session.created_by != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only session creator can end it")

        already_completed = session.status == "completed"
        if not already_completed:
            now = datetime.now(timezone.utc)
            session.status = "completed"
            session.ended_at = now
            if session.started_at:
                session.duration_sec = int((now - session.started_at).total_seconds())

        await db.commit()
        await db.refresh(session)
        logger.info("Session %s ended", session_id)

        # Trigger detailed evaluation once when the session is first completed.
        if not already_completed:
            background_tasks.add_task(scoring_engine.evaluate_session, session.id)

        return SessionResponse.model_validate(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error ending session=%s", session_id)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/{session_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        messages_result = await db.execute(
            select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
        )
        messages = messages_result.scalars().all()

        return TranscriptResponse(
            session_id=session.id,
            mode=session.mode,
            duration_sec=session.duration_sec,
            messages=[MessageResponse.model_validate(m) for m in messages],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting transcript for session=%s", session_id)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

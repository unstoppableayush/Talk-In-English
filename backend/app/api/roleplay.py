"""
Roleplay API — scenarios, sessions, messages, evaluations.

REST endpoints:
  GET  /scenarios           — list predefined scenarios
  POST /start-session       — start a new roleplay session
  POST /send-message        — send a user message and get AI reply
  POST /end-session/{id}    — end session and trigger evaluation
  GET  /report/{id}         — get evaluation report
  GET  /sessions            — list user's roleplay sessions
  GET  /sessions/{id}/messages — get session transcript
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.roleplay import (
    RoleplayEvaluation,
    RoleplayMessage,
    RoleplayScenario,
    RoleplaySession,
)
from app.models.user import User
from app.schemas.models import (
    RoleplayEvaluationResponse,
    RoleplayMessageResponse,
    RoleplayScenarioResponse,
    RoleplaySessionResponse,
    SendRoleplayMessageRequest,
    StartRoleplayRequest,
)
from app.services.roleplay_service import roleplay_engine

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Scenarios ──────────────────────────────────────────────────

@router.get("/scenarios", response_model=list[RoleplayScenarioResponse])
async def list_scenarios(
    category: str | None = None,
    difficulty: str | None = None,
    language: str = "en",
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List available roleplay scenarios."""
    try:
        query = select(RoleplayScenario).where(
            RoleplayScenario.is_active.is_(True),
            RoleplayScenario.language == language,
        )
        if category:
            query = query.where(RoleplayScenario.category == category)
        if difficulty:
            query = query.where(RoleplayScenario.difficulty == difficulty)
        query = query.order_by(RoleplayScenario.title)
        result = await db.execute(query)
        return [RoleplayScenarioResponse.model_validate(s) for s in result.scalars().all()]
    except Exception as e:
        logger.exception("Error listing scenarios")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


# ── Session lifecycle ──────────────────────────────────────────

@router.post("/start-session", response_model=RoleplaySessionResponse, status_code=status.HTTP_201_CREATED)
async def start_session(
    body: StartRoleplayRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a new roleplay session (predefined scenario or custom topic)."""
    try:
        if not body.scenario_id and not body.custom_topic:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide either scenario_id or custom_topic",
            )

        # Resolve scenario info for AI context
        topic = body.custom_topic or "General conversation"
        scenario_desc = "General conversation"
        ai_role = "Conversational partner"
        user_role = "Participant"
        starting_prompt = "Hello! Let's start our conversation. Tell me what you think about this topic."

        if body.scenario_id:
            sc_result = await db.execute(
                select(RoleplayScenario).where(
                    RoleplayScenario.id == body.scenario_id,
                    RoleplayScenario.is_active.is_(True),
                )
            )
            scenario = sc_result.scalar_one_or_none()
            if not scenario:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
            topic = scenario.title
            scenario_desc = scenario.description or scenario.title
            ai_role = scenario.ai_role
            user_role = scenario.user_role
            starting_prompt = scenario.starting_prompt

        session = RoleplaySession(
            user_id=user.id,
            scenario_id=body.scenario_id,
            custom_topic=body.custom_topic,
            difficulty=body.difficulty,
            language=body.language,
        )
        db.add(session)
        await db.flush()

        # Store the AI's opening message
        opening_msg = RoleplayMessage(
            session_id=session.id,
            sender="ai",
            content=starting_prompt,
        )
        db.add(opening_msg)
        await db.commit()
        await db.refresh(session)

        # Initialize AI context for this session
        roleplay_engine.create_context(
            session_id=str(session.id),
            topic=topic,
            scenario_description=scenario_desc,
            ai_role=ai_role,
            user_role=user_role,
            difficulty=body.difficulty,
        )

        return RoleplaySessionResponse.model_validate(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error starting roleplay session")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post("/send-message", response_model=RoleplayMessageResponse)
async def send_message(
    body: SendRoleplayMessageRequest,
    session_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message in an active roleplay session and get AI reply."""
    try:
        # Validate session
        result = await db.execute(
            select(RoleplaySession).where(
                RoleplaySession.id == session_id,
                RoleplaySession.user_id == user.id,
                RoleplaySession.status == "active",
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active session not found")

        # Store user message
        user_msg = RoleplayMessage(session_id=session.id, sender="user", content=body.content)
        db.add(user_msg)
        await db.flush()

        # Generate AI reply
        ai_reply_text = await roleplay_engine.generate_reply(str(session.id), body.content)

        # Store AI message
        ai_msg = RoleplayMessage(session_id=session.id, sender="ai", content=ai_reply_text)
        db.add(ai_msg)
        await db.commit()
        await db.refresh(ai_msg)

        return RoleplayMessageResponse.model_validate(ai_msg)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error sending message in roleplay session=%s", session_id)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post("/end-session/{session_id}", response_model=RoleplaySessionResponse)
async def end_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """End a roleplay session and trigger AI evaluation."""
    try:
        result = await db.execute(
            select(RoleplaySession).where(
                RoleplaySession.id == session_id,
                RoleplaySession.user_id == user.id,
                RoleplaySession.status == "active",
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active session not found")

        now = datetime.now(timezone.utc)
        session.status = "completed"
        session.ended_at = now
        if session.started_at:
            session.duration_sec = int((now - session.started_at).total_seconds())

        await db.commit()
        await db.refresh(session)

        # Clean up AI context and trigger evaluation
        roleplay_engine.remove_context(str(session.id))
        background_tasks.add_task(roleplay_engine.evaluate_session, str(session.id))

        return RoleplaySessionResponse.model_validate(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error ending roleplay session=%s", session_id)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/report/{session_id}", response_model=RoleplayEvaluationResponse)
async def get_report(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the AI evaluation report for a completed session."""
    try:
        result = await db.execute(
            select(RoleplayEvaluation).where(
                RoleplayEvaluation.session_id == session_id,
                RoleplayEvaluation.user_id == user.id,
            )
        )
        evaluation = result.scalar_one_or_none()
        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evaluation not found. It may still be processing.",
            )
        return RoleplayEvaluationResponse.model_validate(evaluation)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting report for session=%s", session_id)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/sessions", response_model=list[RoleplaySessionResponse])
async def list_sessions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's roleplay sessions."""
    try:
        result = await db.execute(
            select(RoleplaySession)
            .where(RoleplaySession.user_id == user.id)
            .order_by(desc(RoleplaySession.started_at))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return [RoleplaySessionResponse.model_validate(s) for s in result.scalars().all()]
    except Exception as e:
        logger.exception("Error listing roleplay sessions")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/sessions/{session_id}/messages", response_model=list[RoleplayMessageResponse])
async def get_session_messages(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the full transcript of a roleplay session."""
    try:
        # Verify ownership
        sess_result = await db.execute(
            select(RoleplaySession).where(
                RoleplaySession.id == session_id,
                RoleplaySession.user_id == user.id,
            )
        )
        if not sess_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        result = await db.execute(
            select(RoleplayMessage)
            .where(RoleplayMessage.session_id == session_id)
            .order_by(RoleplayMessage.created_at)
        )
        return [RoleplayMessageResponse.model_validate(m) for m in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting messages for session=%s", session_id)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

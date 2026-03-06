from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.ai_feedback import AIFeedbackReport
from app.models.evaluation import SessionScore
from app.models.user import User
from app.schemas.models import AIFeedbackResponse, SessionScoreResponse
from app.services.ai_service import scoring_engine

router = APIRouter()


@router.post("/sessions/{session_id}/evaluate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_evaluation(
    session_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Trigger AI evaluation for a completed session (runs in background)."""
    background_tasks.add_task(scoring_engine.evaluate_session, session_id)
    return {"status": "accepted", "message": "Evaluation started"}


@router.get("/sessions/{session_id}/score", response_model=SessionScoreResponse)
async def get_session_score(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SessionScore).where(
            SessionScore.session_id == session_id,
            SessionScore.user_id == user.id,
        )
    )
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Score not found")
    return SessionScoreResponse.model_validate(score)


@router.get("/sessions/{session_id}/feedback", response_model=AIFeedbackResponse)
async def get_session_feedback(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AIFeedbackReport).where(
            AIFeedbackReport.session_id == session_id,
            AIFeedbackReport.user_id == user.id,
        )
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    return AIFeedbackResponse.model_validate(feedback)


@router.get("/history", response_model=list[SessionScoreResponse])
async def get_score_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SessionScore)
        .where(SessionScore.user_id == user.id)
        .order_by(SessionScore.scored_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    scores = result.scalars().all()
    return [SessionScoreResponse.model_validate(s) for s in scores]

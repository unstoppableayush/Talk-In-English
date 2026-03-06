from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.evaluation import ProgressSnapshot, SessionScore
from app.models.session import Session, RoomParticipant
from app.models.user import User
from app.schemas.models import DashboardResponse, DimensionAvg

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Total sessions count
    total_result = await db.execute(
        select(func.count())
        .select_from(RoomParticipant)
        .where(RoomParticipant.user_id == user.id)
    )
    total_sessions = total_result.scalar() or 0

    # Total practice duration (seconds → minutes)
    duration_result = await db.execute(
        select(func.coalesce(func.sum(Session.duration_sec), 0))
        .join(RoomParticipant, RoomParticipant.session_id == Session.id)
        .where(RoomParticipant.user_id == user.id, Session.status == "completed")
    )
    total_duration_sec = duration_result.scalar() or 0

    # Recent sessions (last 30 days)
    recent_result = await db.execute(
        select(func.count())
        .select_from(SessionScore)
        .where(SessionScore.user_id == user.id)
    )
    recent_sessions = recent_result.scalar() or 0

    # Build snapshots from ProgressSnapshot table
    snapshots: dict[str, DimensionAvg] = {}
    for period in ("7d", "30d", "all"):
        snap_result = await db.execute(
            select(ProgressSnapshot)
            .where(ProgressSnapshot.user_id == user.id, ProgressSnapshot.period == period)
            .order_by(ProgressSnapshot.snapshot_date.desc())
            .limit(1)
        )
        snap = snap_result.scalar_one_or_none()
        if snap:
            snapshots[period] = DimensionAvg(
                fluency=snap.fluency_avg,
                clarity=snap.clarity_avg,
                grammar=snap.grammar_avg,
                vocabulary=snap.vocabulary_avg,
                coherence=snap.coherence_avg,
                leadership=snap.leadership_avg,
                engagement=snap.engagement_avg,
                turn_taking=snap.turn_taking_avg,
                overall=snap.overall_avg,
            )
        else:
            snapshots[period] = DimensionAvg()

    return DashboardResponse(
        xp=user.xp or 0,
        streak_days=user.streak_days or 0,
        recent_sessions=recent_sessions,
        total_sessions=total_sessions,
        total_practice_minutes=total_duration_sec // 60,
        snapshots=snapshots,
    )

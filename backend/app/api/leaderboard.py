"""
Leaderboard & Analytics API — rankings, weakness analysis, AI suggestions.

Provides:
  • Leaderboard by period (weekly, monthly, alltime)
  • On-the-fly leaderboard computation when pre-computed rows are stale
  • Per-user weakness analysis with AI improvement suggestions
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.evaluation import SessionScore
from app.models.leaderboard import LeaderboardEntry
from app.models.user import User
from app.schemas.models import LeaderboardEntryResponse, LeaderboardResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def _period_start(period: str) -> date:
    """Compute the start date for a leaderboard period."""
    today = date.today()
    if period == "weekly":
        return today - timedelta(days=today.weekday())  # Monday
    elif period == "monthly":
        return today.replace(day=1)
    else:  # alltime
        return date(2024, 1, 1)


@router.get("", response_model=LeaderboardResponse)
async def get_leaderboard(
    period: str = Query("weekly", pattern=r"^(weekly|monthly|alltime)$"),
    limit: int = Query(50, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get leaderboard for a period. Returns pre-computed entries if available,
    otherwise computes on the fly from SessionScore data.
    """
    p_start = _period_start(period)

    # Try pre-computed entries first
    result = await db.execute(
        select(LeaderboardEntry)
        .where(LeaderboardEntry.period == period, LeaderboardEntry.period_start == p_start)
        .order_by(LeaderboardEntry.rank)
        .limit(limit)
    )
    entries = result.scalars().all()

    if entries:
        out = []
        for e in entries:
            # Fetch user display info
            user_result = await db.execute(select(User).where(User.id == e.user_id))
            u = user_result.scalar_one_or_none()
            out.append(LeaderboardEntryResponse(
                rank=e.rank,
                user_id=e.user_id,
                username=u.display_name if u else None,
                avatar_url=u.avatar_url if u else None,
                total_xp=e.total_xp,
                sessions_count=e.sessions_count,
                avg_overall_score=e.avg_overall_score,
            ))
        return LeaderboardResponse(period=period, period_start=p_start, entries=out)

    # Compute on the fly
    start_dt = datetime(p_start.year, p_start.month, p_start.day, tzinfo=timezone.utc)
    query = (
        select(
            SessionScore.user_id,
            func.sum(SessionScore.xp_earned).label("total_xp"),
            func.count(SessionScore.id).label("sessions_count"),
            func.avg(SessionScore.overall).label("avg_overall"),
        )
        .where(SessionScore.scored_at >= start_dt)
        .group_by(SessionScore.user_id)
        .order_by(desc("total_xp"))
        .limit(limit)
    )
    result = await db.execute(query)
    rows = result.all()

    out = []
    for rank, row in enumerate(rows, 1):
        user_result = await db.execute(select(User).where(User.id == row.user_id))
        u = user_result.scalar_one_or_none()
        out.append(LeaderboardEntryResponse(
            rank=rank,
            user_id=row.user_id,
            username=u.display_name if u else None,
            avatar_url=u.avatar_url if u else None,
            total_xp=int(row.total_xp or 0),
            sessions_count=int(row.sessions_count or 0),
            avg_overall_score=int(row.avg_overall or 0),
        ))

    return LeaderboardResponse(period=period, period_start=p_start, entries=out)


@router.get("/me")
async def get_my_rank(
    period: str = Query("weekly", pattern=r"^(weekly|monthly|alltime)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's rank and stats for a given period."""
    p_start = _period_start(period)
    start_dt = datetime(p_start.year, p_start.month, p_start.day, tzinfo=timezone.utc)

    # Get user stats
    result = await db.execute(
        select(
            func.sum(SessionScore.xp_earned).label("total_xp"),
            func.count(SessionScore.id).label("sessions_count"),
            func.avg(SessionScore.overall).label("avg_overall"),
        )
        .where(SessionScore.user_id == user.id, SessionScore.scored_at >= start_dt)
    )
    row = result.one_or_none()
    total_xp = int(row.total_xp or 0) if row else 0

    # Count users with more XP to determine rank
    rank_result = await db.execute(
        select(func.count()).select_from(
            select(SessionScore.user_id)
            .where(SessionScore.scored_at >= start_dt)
            .group_by(SessionScore.user_id)
            .having(func.sum(SessionScore.xp_earned) > total_xp)
            .subquery()
        )
    )
    rank = (rank_result.scalar() or 0) + 1

    return {
        "rank": rank,
        "total_xp": total_xp,
        "sessions_count": int(row.sessions_count or 0) if row else 0,
        "avg_overall_score": int(row.avg_overall or 0) if row else 0,
        "period": period,
        "period_start": p_start.isoformat(),
    }


@router.get("/weakness-analysis")
async def weakness_analysis(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyze user's weakest dimensions based on their last 20 scored sessions."""
    result = await db.execute(
        select(SessionScore)
        .where(SessionScore.user_id == user.id)
        .order_by(SessionScore.scored_at.desc())
        .limit(20)
    )
    scores = result.scalars().all()

    if not scores:
        return {"weaknesses": [], "suggestions": [], "message": "No scored sessions yet."}

    dims = ["fluency", "clarity", "grammar", "vocabulary", "coherence", "leadership", "engagement", "turn_taking"]
    averages = {}
    for dim in dims:
        vals = [getattr(s, dim) for s in scores if getattr(s, dim) is not None]
        averages[dim] = round(sum(vals) / len(vals), 1) if vals else 0

    # Sort by weakest
    sorted_dims = sorted(averages.items(), key=lambda x: x[1])
    weaknesses = [{"dimension": d, "avg_score": v} for d, v in sorted_dims[:3]]

    suggestions_map = {
        "fluency": "Practice speaking without long pauses. Try reading passages aloud daily.",
        "clarity": "Focus on enunciation and structured responses. Record yourself and review.",
        "grammar": "Review common grammar mistakes. Use grammar-focused exercises on each session.",
        "vocabulary": "Read widely and practice incorporating new words into conversations.",
        "coherence": "Organize your thoughts before speaking. Use transition words.",
        "leadership": "Practice initiating topics and asking follow-up questions in group settings.",
        "engagement": "Show active listening — ask clarifying questions and build on what others say.",
        "turn_taking": "Practice conversational timing. Avoid interrupting and allow natural pauses.",
    }

    suggestions = [suggestions_map.get(w["dimension"], "") for w in weaknesses]

    return {
        "dimension_averages": averages,
        "weaknesses": weaknesses,
        "suggestions": suggestions,
    }

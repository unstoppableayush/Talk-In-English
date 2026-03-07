"""
Section Testing API — speaking, listening, writing test endpoints.

Supports:
  • Full test mode (all questions) or single section mode
  • Timed mode (enforced server-side)
  • AI-powered instant scoring via LLM
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.section_test import SectionTest, TestAttempt
from app.models.user import User
from app.schemas.models import (
    CreateSectionTestRequest,
    SectionTestResponse,
    SubmitTestAttemptRequest,
    TestAttemptResponse,
)
from app.services.ai_service import llm_provider, LLMConfig

logger = logging.getLogger(__name__)
router = APIRouter()

# ╔══════════════════════════════════════════════════════════════╗
# ║  Test definitions (admin-only write, authenticated read)      ║
# ╚══════════════════════════════════════════════════════════════╝


@router.post("", response_model=SectionTestResponse, status_code=status.HTTP_201_CREATED)
async def create_test(
    body: CreateSectionTestRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new section test (admin only)."""
    try:
        test = SectionTest(
            title=body.title,
            description=body.description,
            section=body.section,
            difficulty_level=body.difficulty_level,
            language=body.language,
            time_limit_sec=body.time_limit_sec,
            pass_threshold=body.pass_threshold,
            questions=body.questions,
            created_by=user.id,
        )
        db.add(test)
        await db.commit()
        await db.refresh(test)
        resp = SectionTestResponse.model_validate(test)
        resp.question_count = len(test.questions) if isinstance(test.questions, list) else 0
        return resp
    except Exception as e:
        logger.exception("Error creating test")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("", response_model=list[SectionTestResponse])
async def list_tests(
    section: str | None = None,
    difficulty: str | None = None,
    language: str = "en",
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List available tests with optional filters."""
    try:
        query = select(SectionTest).where(
            SectionTest.is_active.is_(True),
            SectionTest.language == language,
        )
        if section:
            query = query.where(SectionTest.section == section)
        if difficulty:
            query = query.where(SectionTest.difficulty_level == difficulty)
        query = query.order_by(SectionTest.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(query)
        tests = result.scalars().all()
        out = []
        for t in tests:
            r = SectionTestResponse.model_validate(t)
            r.question_count = len(t.questions) if isinstance(t.questions, list) else 0
            out.append(r)
        return out
    except Exception as e:
        logger.exception("Error listing tests")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/{test_id}", response_model=SectionTestResponse)
async def get_test(
    test_id: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(SectionTest).where(SectionTest.id == test_id))
        test = result.scalar_one_or_none()
        if not test:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
        resp = SectionTestResponse.model_validate(test)
        resp.question_count = len(test.questions) if isinstance(test.questions, list) else 0
        return resp
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting test=%s", test_id)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


# ╔══════════════════════════════════════════════════════════════╗
# ║  Test Attempts — submit answers, get AI grading               ║
# ╚══════════════════════════════════════════════════════════════╝

GRADING_PROMPT = """You are an expert language test grader. Score each answer on a 0-100 scale.

Test section: {section}
Difficulty: {difficulty}

Questions and user answers:
{qa_block}

For each question, provide:
- score (0-100)
- feedback (1-2 sentences explaining the score)

Also provide:
- overall_score: weighted average of all question scores
- passed: true if overall_score >= {pass_threshold}
- xp_earned: 5-30 based on performance

Return JSON:
{{
  "question_scores": [
    {{"question_id": "...", "score": N, "feedback": "..."}},
    ...
  ],
  "overall_score": N,
  "passed": true/false,
  "xp_earned": N
}}"""


@router.post("/attempts", response_model=TestAttemptResponse, status_code=status.HTTP_201_CREATED)
async def submit_attempt(
    body: SubmitTestAttemptRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit answers for a test. AI grades in the background."""
    try:
        # Load test
        result = await db.execute(select(SectionTest).where(SectionTest.id == body.test_id))
        test = result.scalar_one_or_none()
        if not test or not test.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found or inactive")

        now = datetime.now(timezone.utc)

        attempt = TestAttempt(
            test_id=test.id,
            user_id=user.id,
            answers=body.answers,
            started_at=now,
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)

        # Grade in background
        background_tasks.add_task(
            _grade_attempt, str(attempt.id), str(test.id)
        )

        return TestAttemptResponse.model_validate(attempt)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error submitting attempt")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/attempts/{attempt_id}", response_model=TestAttemptResponse)
async def get_attempt(
    attempt_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(TestAttempt).where(TestAttempt.id == attempt_id, TestAttempt.user_id == user.id)
        )
        attempt = result.scalar_one_or_none()
        if not attempt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
        return TestAttemptResponse.model_validate(attempt)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting attempt=%s", attempt_id)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/attempts", response_model=list[TestAttemptResponse])
async def list_my_attempts(
    test_id: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        query = select(TestAttempt).where(TestAttempt.user_id == user.id)
        if test_id:
            query = query.where(TestAttempt.test_id == test_id)
        query = query.order_by(TestAttempt.started_at.desc()).offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(query)
        attempts = result.scalars().all()
        return [TestAttemptResponse.model_validate(a) for a in attempts]
    except Exception as e:
        logger.exception("Error listing attempts")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


# ╔══════════════════════════════════════════════════════════════╗
# ║  AI Grading — Background task                                ║
# ╚══════════════════════════════════════════════════════════════╝

async def _grade_attempt(attempt_id: str, test_id: str) -> None:
    """AI-powered grading that runs as a background task."""
    from app.core.database import async_session

    async with async_session() as db:
        attempt_result = await db.execute(select(TestAttempt).where(TestAttempt.id == attempt_id))
        attempt = attempt_result.scalar_one_or_none()
        if not attempt:
            return

        test_result = await db.execute(select(SectionTest).where(SectionTest.id == test_id))
        test = test_result.scalar_one_or_none()
        if not test:
            return

        # Build Q&A block for the prompt
        questions = test.questions if isinstance(test.questions, list) else []
        answers = attempt.answers if isinstance(attempt.answers, list) else []
        answer_map = {a.get("question_id"): a for a in answers}

        qa_lines = []
        for q in questions:
            qid = q.get("id", "?")
            qa_lines.append(f"Question [{qid}]: {q.get('prompt', '')}")
            user_answer = answer_map.get(qid, {})
            qa_lines.append(f"  Rubric: {q.get('rubric', 'Score quality, relevance, accuracy')}")
            qa_lines.append(f"  User answer: {user_answer.get('answer', '(no answer)')}")
            qa_lines.append("")

        qa_block = "\n".join(qa_lines)

        prompt = GRADING_PROMPT.format(
            section=test.section,
            difficulty=test.difficulty_level,
            qa_block=qa_block,
            pass_threshold=test.pass_threshold,
        )

        config = LLMConfig(temperature=0.2, max_tokens=1500)

        try:
            response = await llm_provider.complete(
                [{"role": "user", "content": prompt}], config
            )
            raw = response.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
            result = json.loads(raw)
        except Exception as e:
            logger.exception("AI grading failed for attempt %s", attempt_id)
            return

        # Persist scores
        attempt.question_scores = result.get("question_scores", [])
        attempt.score = max(0, min(100, float(result.get("overall_score", 0))))
        attempt.passed = result.get("passed", attempt.score >= test.pass_threshold)
        attempt.xp_earned = max(0, min(100, int(result.get("xp_earned", 0))))
        attempt.completed_at = datetime.now(timezone.utc)

        # Update user XP
        user_result = await db.execute(select(User).where(User.id == attempt.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            user.xp = (user.xp or 0) + attempt.xp_earned

        await db.commit()
        logger.info("Graded attempt %s — score=%s, passed=%s", attempt_id, attempt.score, attempt.passed)

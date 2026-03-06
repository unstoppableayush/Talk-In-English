"""
Roleplay AI Service — conversation management + end-of-session evaluation.

Manages per-session conversation history and generates contextual AI replies
that behave as a human conversational partner in roleplay scenarios.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import async_session
from app.models.roleplay import RoleplayEvaluation, RoleplayMessage, RoleplaySession, RoleplayScenario
from app.models.user import User
from app.services.ai_service import LLMConfig, llm_provider

logger = logging.getLogger(__name__)

# ── Prompt Templates ──────────────────────────────────────────

ROLEPLAY_SYSTEM_PROMPT = """You are a human conversational partner in a role-play session.

Topic: {topic}
Scenario: {scenario_description}
Your role: {ai_role}
User's role: {user_role}
Difficulty level: {difficulty}

Rules:
- Respond naturally like a real human
- Keep responses short and conversational (2-4 sentences)
- Ask open-ended follow-up questions
- Encourage the user to speak more and explain their ideas
- Challenge the user with thoughtful follow-up questions
- Maintain topic context throughout the conversation
- Stay in character as {ai_role}
- Adapt language complexity to {difficulty} level

Conversation history:
{chat_history}

Respond as a human conversational partner."""


ROLEPLAY_EVAL_PROMPT = """You are an expert language skills evaluator. Analyze the following role-play conversation \
transcript and evaluate the USER's speaking performance.

Scenario: {scenario_description}
Difficulty: {difficulty}
Topic: {topic}

Evaluate the user on these dimensions (score each 0-100):
1. fluency_score — smoothness and natural pace of speech
2. grammar_score — correctness of grammar and sentence structure
3. vocabulary_score — range and appropriateness of vocabulary
4. confidence_score — assertiveness and willingness to express ideas
5. clarity_score — how clear and understandable the user's messages are
6. relevance_score — staying on topic and responding appropriately
7. consistency_score — maintaining coherent ideas throughout the conversation

Also provide:
- overall_score: weighted average (0-100)
- xp_earned: 5-50 based on effort and quality
- strengths: list of 2-4 bullet points
- weaknesses: list of 2-4 bullet points
- improvement_suggestions: list of 2-3 actionable tips
- filler_words: object mapping detected filler words to their count (e.g. {{"um": 3, "uh": 2, "like": 5}})

Respond with JSON only:
{{
  "fluency_score": N,
  "grammar_score": N,
  "vocabulary_score": N,
  "confidence_score": N,
  "clarity_score": N,
  "relevance_score": N,
  "consistency_score": N,
  "overall_score": N,
  "xp_earned": N,
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "improvement_suggestions": ["...", "..."],
  "filler_words": {{"word": count}}
}}

Transcript:
{transcript}"""


# ── Conversation Context ──────────────────────────────────────

@dataclass
class RoleplayContext:
    session_id: str
    topic: str
    scenario_description: str
    ai_role: str
    user_role: str
    difficulty: str
    history: list[dict] = field(default_factory=list)
    max_history: int = 40


class RoleplayEngine:
    """Manages roleplay conversations and evaluations."""

    def __init__(self) -> None:
        self._contexts: dict[str, RoleplayContext] = {}

    def create_context(
        self,
        session_id: str,
        topic: str,
        scenario_description: str = "General conversation",
        ai_role: str = "Conversational partner",
        user_role: str = "Participant",
        difficulty: str = "intermediate",
    ) -> None:
        self._contexts[session_id] = RoleplayContext(
            session_id=session_id,
            topic=topic,
            scenario_description=scenario_description,
            ai_role=ai_role,
            user_role=user_role,
            difficulty=difficulty,
        )

    def remove_context(self, session_id: str) -> None:
        self._contexts.pop(session_id, None)

    async def generate_reply(self, session_id: str, user_message: str) -> str:
        """Generate an AI reply to the user's message in the roleplay."""
        ctx = self._contexts.get(session_id)
        if not ctx:
            return "Session context not found. Please restart the roleplay."

        # Add user message to history
        ctx.history.append({"role": "user", "content": user_message})
        if len(ctx.history) > ctx.max_history:
            ctx.history = ctx.history[-ctx.max_history:]

        # Build chat history for prompt
        history_text = "\n".join(
            f"{'User' if m['role'] == 'user' else 'AI'}: {m['content']}"
            for m in ctx.history
        )

        system_prompt = ROLEPLAY_SYSTEM_PROMPT.format(
            topic=ctx.topic,
            scenario_description=ctx.scenario_description,
            ai_role=ctx.ai_role,
            user_role=ctx.user_role,
            difficulty=ctx.difficulty,
            chat_history=history_text,
        )

        config = LLMConfig(
            temperature=0.7,
            max_tokens=300,
            system_prompt=system_prompt,
        )

        try:
            response = await llm_provider.complete(
                [{"role": "user", "content": user_message}], config
            )
            ai_reply = response.content
        except Exception:
            logger.exception("Roleplay AI reply failed for session %s", session_id)
            ai_reply = "I'm sorry, I had trouble processing that. Could you repeat?"

        # Add AI reply to history
        ctx.history.append({"role": "assistant", "content": ai_reply})
        return ai_reply

    async def evaluate_session(self, session_id: str) -> dict | None:
        """
        Evaluate a completed roleplay session. Loads transcript from DB,
        sends to LLM, persists RoleplayEvaluation, updates user XP.
        """
        async with async_session() as db:
            # Load session
            sess_result = await db.execute(
                select(RoleplaySession).where(RoleplaySession.id == session_id)
            )
            session = sess_result.scalar_one_or_none()
            if not session:
                logger.warning("Roleplay session %s not found", session_id)
                return None

            # Load messages
            msg_result = await db.execute(
                select(RoleplayMessage)
                .where(RoleplayMessage.session_id == session.id)
                .order_by(RoleplayMessage.created_at)
            )
            messages = msg_result.scalars().all()
            if not messages:
                logger.info("No messages in roleplay session %s", session_id)
                return None

            # Build transcript
            lines = [f"{'User' if m.sender == 'user' else 'AI'}: {m.content}" for m in messages]
            transcript = "\n".join(lines)

            # Determine topic/scenario info
            topic = session.custom_topic or "General conversation"
            scenario_desc = "General conversation"
            if session.scenario_id:
                sc_result = await db.execute(
                    select(RoleplayScenario).where(RoleplayScenario.id == session.scenario_id)
                )
                scenario = sc_result.scalar_one_or_none()
                if scenario:
                    topic = scenario.title
                    scenario_desc = scenario.description or scenario.title

            prompt = ROLEPLAY_EVAL_PROMPT.format(
                scenario_description=scenario_desc,
                difficulty=session.difficulty,
                topic=topic,
                transcript=transcript,
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
            except Exception:
                logger.exception("Roleplay evaluation failed for session %s", session_id)
                return None

            def _clamp(v, lo=0, hi=100):
                return max(lo, min(hi, int(v)))

            evaluation = RoleplayEvaluation(
                session_id=session.id,
                user_id=session.user_id,
                fluency_score=_clamp(result.get("fluency_score", 0)),
                grammar_score=_clamp(result.get("grammar_score", 0)),
                vocabulary_score=_clamp(result.get("vocabulary_score", 0)),
                confidence_score=_clamp(result.get("confidence_score", 0)),
                clarity_score=_clamp(result.get("clarity_score", 0)),
                relevance_score=_clamp(result.get("relevance_score", 0)),
                consistency_score=_clamp(result.get("consistency_score", 0)),
                overall_score=round(max(0, min(100, float(result.get("overall_score", 0)))), 1),
                xp_earned=_clamp(result.get("xp_earned", 0), 0, 100),
                strengths=result.get("strengths", []),
                weaknesses=result.get("weaknesses", []),
                improvement_suggestions=result.get("improvement_suggestions", []),
                filler_words=result.get("filler_words", {}),
                raw_response=result,
                model_used=config.model,
            )
            db.add(evaluation)

            # Update user XP
            user_result = await db.execute(select(User).where(User.id == session.user_id))
            user = user_result.scalar_one_or_none()
            if user:
                user.xp = (user.xp or 0) + evaluation.xp_earned

            await db.commit()
            logger.info("Roleplay evaluation complete for session %s", session_id)
            return result


# Singleton
roleplay_engine = RoleplayEngine()

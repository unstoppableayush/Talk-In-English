"""
AI Service — LLM abstraction layer.

Provides a unified interface for conversation, moderation, and evaluation
across multiple LLM providers (OpenAI, Anthropic).  Includes:
  • ConversationManager – session-based context memory for 1-on-1 AI chats
  • ModerationService – real-time group discussion moderation
  • ScoringEngine     – end-of-session structured JSON evaluation
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator

from openai import AsyncOpenAI
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session
from app.models.ai_feedback import AIFeedbackReport
from app.models.evaluation import SessionScore
from app.models.message import Message
from app.models.session import Session
from app.models.user import User

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  LLM Provider Abstraction                                    ║
# ╚══════════════════════════════════════════════════════════════╝


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    latency_ms: int


@dataclass
class LLMConfig:
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 1024
    system_prompt: str = ""


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict], config: LLMConfig) -> LLMResponse: ...

    @abstractmethod
    async def stream(self, messages: list[dict], config: LLMConfig) -> AsyncIterator[str]: ...


class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.name = "openai"

    async def complete(self, messages: list[dict], config: LLMConfig) -> LLMResponse:
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}, *messages]

        start = time.monotonic()
        response = await self.client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        latency = int((time.monotonic() - start) * 1000)

        return LLMResponse(
            content=response.choices[0].message.content or "",
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            model=config.model,
            latency_ms=latency,
        )

    async def stream(self, messages: list[dict], config: LLMConfig) -> AsyncIterator[str]:
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}, *messages]

        response = await self.client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class GrokProvider(LLMProvider):
    """xAI Grok — uses OpenAI-compatible API."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.GROK_API_KEY,
            base_url="https://api.x.ai/v1",
        )
        self.name = "grok"

    async def complete(self, messages: list[dict], config: LLMConfig) -> LLMResponse:
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}, *messages]

        model = "grok-3-latest"
        start = time.monotonic()
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        latency = int((time.monotonic() - start) * 1000)

        return LLMResponse(
            content=response.choices[0].message.content or "",
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            model=model,
            latency_ms=latency,
        )

    async def stream(self, messages: list[dict], config: LLMConfig) -> AsyncIterator[str]:
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}, *messages]

        response = await self.client.chat.completions.create(
            model="grok-3-latest",
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class GeminiProvider(LLMProvider):
    """Google Gemini — uses OpenAI-compatible endpoint."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        self.name = "gemini"

    async def complete(self, messages: list[dict], config: LLMConfig) -> LLMResponse:
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}, *messages]

        model = "gemini-2.0-flash"
        start = time.monotonic()
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        latency = int((time.monotonic() - start) * 1000)

        return LLMResponse(
            content=response.choices[0].message.content or "",
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            model=model,
            latency_ms=latency,
        )

    async def stream(self, messages: list[dict], config: LLMConfig) -> AsyncIterator[str]:
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}, *messages]

        response = await self.client.chat.completions.create(
            model="gemini-2.0-flash",
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class DeepSeekProvider(LLMProvider):
    """DeepSeek — uses OpenAI-compatible API."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
        self.name = "deepseek"

    async def complete(self, messages: list[dict], config: LLMConfig) -> LLMResponse:
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}, *messages]

        model = "deepseek-chat"
        start = time.monotonic()
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        latency = int((time.monotonic() - start) * 1000)

        return LLMResponse(
            content=response.choices[0].message.content or "",
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            model=model,
            latency_ms=latency,
        )

    async def stream(self, messages: list[dict], config: LLMConfig) -> AsyncIterator[str]:
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}, *messages]

        response = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# ── Provider registry ────────────────────────────────────────────

_PROVIDER_MAP: dict[str, tuple[str, type[LLMProvider]]] = {
    "openai": ("OPENAI_API_KEY", OpenAIProvider),
    "grok": ("GROK_API_KEY", GrokProvider),
    "gemini": ("GEMINI_API_KEY", GeminiProvider),
    "deepseek": ("DEEPSEEK_API_KEY", DeepSeekProvider),
}


class FallbackLLMProvider(LLMProvider):
    """
    Wraps multiple LLM providers and tries them in priority order.
    Skips providers whose API keys are missing. If one fails at runtime,
    automatically retries with the next available provider.
    """

    def __init__(self) -> None:
        self._providers: list[LLMProvider] = []
        order = [p.strip().lower() for p in settings.LLM_PROVIDER_ORDER.split(",") if p.strip()]

        for name in order:
            entry = _PROVIDER_MAP.get(name)
            if not entry:
                logger.warning("Unknown LLM provider '%s' in LLM_PROVIDER_ORDER, skipping", name)
                continue
            key_attr, cls = entry
            key_value = getattr(settings, key_attr, "")
            if key_value:
                self._providers.append(cls())
                logger.info("LLM provider '%s' registered (key present)", name)
            else:
                logger.info("LLM provider '%s' skipped (no API key)", name)

        if not self._providers:
            logger.error("No LLM providers configured! Set at least one API key.")

    @property
    def active_provider_name(self) -> str:
        if self._providers:
            return getattr(self._providers[0], "name", "unknown")
        return "none"

    async def complete(self, messages: list[dict], config: LLMConfig) -> LLMResponse:
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                result = await provider.complete(messages, config)
                return result
            except Exception as exc:
                name = getattr(provider, "name", type(provider).__name__)
                logger.warning("LLM provider '%s' failed: %s — trying next", name, exc)
                last_error = exc

        raise RuntimeError(
            f"All LLM providers failed. Last error: {last_error}"
        ) from last_error

    async def stream(self, messages: list[dict], config: LLMConfig) -> AsyncIterator[str]:
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                async for chunk in provider.stream(messages, config):
                    yield chunk
                return  # success — stop trying others
            except Exception as exc:
                name = getattr(provider, "name", type(provider).__name__)
                logger.warning("LLM stream provider '%s' failed: %s — trying next", name, exc)
                last_error = exc

        raise RuntimeError(
            f"All LLM stream providers failed. Last error: {last_error}"
        ) from last_error


# Singleton — the rest of the app imports this
llm_provider = FallbackLLMProvider()


# ╔══════════════════════════════════════════════════════════════╗
# ║  Prompt Templates                                            ║
# ╚══════════════════════════════════════════════════════════════╝

CONVERSATION_SYSTEM_PROMPT = """You are a friendly and encouraging language practice partner. \
Your role is to engage in natural conversation while helping the user improve their {target_language} skills. \
Adapt your language complexity to match the user's level: {difficulty}. \
Topic: {topic}. \
Keep responses concise (2-4 sentences). Ask follow-up questions to keep the conversation going. \
Gently correct major errors by rephrasing the user's point correctly."""

MODERATION_SYSTEM_PROMPT = """You are a conversation moderator for a language practice room. \
There are up to {max_speakers} speakers discussing: {topic}. \
Monitor the discussion and intervene only when necessary:
- Redirect off-topic discussions
- Encourage quiet participants who haven't spoken recently
- Flag inappropriate content
- Suggest new discussion angles when conversation stalls
- Keep the conversation balanced — if one user dominates, politely invite others

Respond with a JSON object:
{{"action": "none"|"redirect"|"encourage"|"warn"|"suggest_topic", "message": "...", "target_user": null|"user_display_name"}}

If no intervention is needed, respond with: {{"action": "none"}}"""

SILENT_MONITOR_PROMPT = """You are silently observing a 1-on-1 language practice conversation between two users. \
Do NOT generate any messages to the users. \
You will analyze the full transcript after the session ends."""

EVALUATION_SYSTEM_PROMPT = """You are an expert language skills evaluator. Analyze the conversation transcript below \
and provide scores (0-100) for each skill dimension for each user.

Score each dimension:
- fluency: smoothness and natural pace of speech
- clarity: how understandable the user's messages are
- grammar: correctness of grammar and sentence structure
- vocabulary: range and appropriateness of vocabulary
- coherence: logical flow and connection between ideas
- leadership: ability to guide / advance the conversation (0 for 1-on-1 AI)
- engagement: active participation and responsiveness
- turn_taking: appropriate conversation flow, not dominating

Also provide:
- overall: weighted average (auto-calculated, but provide your holistic assessment)
- xp_earned: 5-50 points based on effort and quality
- strengths: list of 2-4 short bullet points
- improvement_areas: list of 2-4 short bullet points
- suggested_exercises: list of 2-3 actionable practice suggestions
- dimension_feedback: object mapping each dimension name to a 1-2 sentence explanation
- summary: 3-5 sentence overall feedback paragraph

Respond with JSON:
{{
    "users": {{
        "<user_id>": {{
            "fluency": N, "clarity": N, "grammar": N, "vocabulary": N,
            "coherence": N, "leadership": N, "engagement": N, "turn_taking": N,
            "overall": N, "xp_earned": N,
            "strengths": ["...", "..."],
            "improvement_areas": ["...", "..."],
            "suggested_exercises": ["...", "..."],
            "dimension_feedback": {{"fluency": "...", "clarity": "...", ...}},
            "summary": "..."
        }}
    }}
}}

Transcript:
{transcript}"""


# ╔══════════════════════════════════════════════════════════════╗
# ║  Conversation Manager — Session-based context memory          ║
# ╚══════════════════════════════════════════════════════════════╝


@dataclass
class ConversationContext:
    session_id: str
    mode: str
    topic: str
    difficulty: str
    target_language: str
    history: list[dict] = field(default_factory=list)
    max_history: int = 50  # Keep last N messages to stay within token limits


class ConversationManager:
    """Maintains per-session conversation history and generates AI responses."""

    def __init__(self) -> None:
        self._contexts: dict[str, ConversationContext] = {}

    def get_or_create_context(
        self,
        session_id: str,
        mode: str = "ai_1on1",
        topic: str = "General conversation",
        difficulty: str = "intermediate",
        target_language: str = "English",
    ) -> ConversationContext:
        if session_id not in self._contexts:
            self._contexts[session_id] = ConversationContext(
                session_id=session_id,
                mode=mode,
                topic=topic,
                difficulty=difficulty,
                target_language=target_language,
            )
        return self._contexts[session_id]

    def remove_context(self, session_id: str) -> None:
        self._contexts.pop(session_id, None)

    async def get_ai_reply(self, session_id: str, user_message: str, user_name: str) -> str:
        """Generate an AI response for a 1-on-1 AI conversation."""
        ctx = self._contexts.get(session_id)
        if not ctx:
            return ""

        # Append user message to history
        ctx.history.append({"role": "user", "content": f"[{user_name}]: {user_message}"})

        # Trim to max history
        if len(ctx.history) > ctx.max_history:
            ctx.history = ctx.history[-ctx.max_history:]

        config = LLMConfig(
            system_prompt=CONVERSATION_SYSTEM_PROMPT.format(
                target_language=ctx.target_language,
                difficulty=ctx.difficulty,
                topic=ctx.topic,
            ),
            temperature=0.8,
            max_tokens=300,
        )

        try:
            response = await llm_provider.complete(ctx.history, config)
            # Append AI reply to history
            ctx.history.append({"role": "assistant", "content": response.content})
            return response.content
        except Exception:
            logger.exception("AI conversation error for session %s", session_id)
            return ""


# Singleton
conversation_manager = ConversationManager()


# ╔══════════════════════════════════════════════════════════════╗
# ║  Moderation Service — Real-time group discussion moderation   ║
# ╚══════════════════════════════════════════════════════════════╝


@dataclass
class ModerationAction:
    action: str  # "none", "redirect", "encourage", "warn", "suggest_topic"
    message: str
    target_user: str | None


class ModerationService:
    """Analyses recent messages in a public room and decides whether to intervene."""

    def __init__(self) -> None:
        self._recent: dict[str, list[dict]] = {}  # session_id → last N messages

    def add_message(self, session_id: str, user_name: str, content: str) -> None:
        if session_id not in self._recent:
            self._recent[session_id] = []
        self._recent[session_id].append({"user": user_name, "content": content})
        # Keep last 20 messages for context
        self._recent[session_id] = self._recent[session_id][-20:]

    def clear(self, session_id: str) -> None:
        self._recent.pop(session_id, None)

    async def check_moderation(
        self, session_id: str, topic: str, max_speakers: int = 5
    ) -> ModerationAction | None:
        """Ask LLM whether moderation is needed based on recent messages."""
        messages = self._recent.get(session_id, [])
        if len(messages) < 3:
            return None  # Not enough context yet

        transcript_lines = [f"{m['user']}: {m['content']}" for m in messages]
        transcript_text = "\n".join(transcript_lines)

        config = LLMConfig(
            system_prompt=MODERATION_SYSTEM_PROMPT.format(
                topic=topic, max_speakers=max_speakers
            ),
            temperature=0.3,
            max_tokens=200,
        )

        try:
            response = await llm_provider.complete(
                [{"role": "user", "content": transcript_text}], config
            )
            parsed = json.loads(response.content)
            if parsed.get("action", "none") == "none":
                return None
            return ModerationAction(
                action=parsed["action"],
                message=parsed.get("message", ""),
                target_user=parsed.get("target_user"),
            )
        except Exception:
            logger.debug("Moderation check failed for session %s", session_id, exc_info=True)
            return None


# Singleton
moderation_service = ModerationService()


# ╔══════════════════════════════════════════════════════════════╗
# ║  Scoring Engine — End-of-session structured evaluation        ║
# ╚══════════════════════════════════════════════════════════════╝

SCORE_DIMENSIONS = [
    "fluency", "clarity", "grammar", "vocabulary",
    "coherence", "leadership", "engagement", "turn_taking",
]


class ScoringEngine:
    """
    Evaluates a completed session by feeding the full transcript to the LLM
    and persisting SessionScore + AIFeedbackReport rows.
    """

    async def evaluate_session(self, session_id: str) -> list[str]:
        """
        Run AI evaluation on a completed session.
        Returns list of user_ids that were scored.
        """
        async with async_session() as db:
            # 1. Load session
            sess_result = await db.execute(select(Session).where(Session.id == session_id))
            session = sess_result.scalar_one_or_none()
            if not session:
                logger.warning("Session %s not found for evaluation", session_id)
                return []

            # 2. Load all messages
            msg_result = await db.execute(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at)
            )
            messages = msg_result.scalars().all()
            if not messages:
                logger.info("No messages in session %s, skipping evaluation", session_id)
                return []

            # 3. Build transcript for the LLM
            user_ids = set()
            lines: list[str] = []
            for msg in messages:
                if msg.sender_type == "user":
                    user_ids.add(str(msg.sender_id))
                tag = f"[{msg.sender_type}:{msg.sender_id}]"
                lines.append(f"{tag} {msg.content}")

            if not user_ids:
                return []

            transcript = "\n".join(lines)

            # 4. Call LLM for evaluation
            config = LLMConfig(
                temperature=0.2,
                max_tokens=2000,
                system_prompt="",
            )
            prompt = EVALUATION_SYSTEM_PROMPT.format(transcript=transcript)

            try:
                response = await llm_provider.complete(
                    [{"role": "user", "content": prompt}], config
                )
                # Strip markdown code fences if present
                raw = response.content.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                    if raw.endswith("```"):
                        raw = raw[:-3]
                result = json.loads(raw)
            except Exception:
                logger.exception("AI scoring failed for session %s", session_id)
                return []

            # 5. Persist scores and feedback
            scored_users: list[str] = []
            users_data = result.get("users", {})

            for uid_str, scores in users_data.items():
                if uid_str not in user_ids:
                    continue

                uid = uuid.UUID(uid_str)

                # -- SessionScore --
                def _clamp(v: int | float, lo: int = 0, hi: int = 100) -> int:
                    return max(lo, min(hi, int(v)))

                session_score = SessionScore(
                    session_id=session.id,
                    user_id=uid,
                    fluency=_clamp(scores.get("fluency", 0)),
                    clarity=_clamp(scores.get("clarity", 0)),
                    grammar=_clamp(scores.get("grammar", 0)),
                    vocabulary=_clamp(scores.get("vocabulary", 0)),
                    coherence=_clamp(scores.get("coherence", 0)),
                    leadership=_clamp(scores.get("leadership", 0)),
                    engagement=_clamp(scores.get("engagement", 0)),
                    turn_taking=_clamp(scores.get("turn_taking", 0)),
                    overall=_clamp(scores.get("overall", 0)),
                    xp_earned=_clamp(scores.get("xp_earned", 0), 0, 500),
                )
                db.add(session_score)

                # -- AIFeedbackReport --
                feedback = AIFeedbackReport(
                    session_id=session.id,
                    user_id=uid,
                    dimension_feedback=scores.get("dimension_feedback", {}),
                    strengths=scores.get("strengths", []),
                    improvement_areas=scores.get("improvement_areas", []),
                    suggested_exercises=scores.get("suggested_exercises", []),
                    summary=scores.get("summary", ""),
                    raw_response=scores,
                    model_used=response.model,
                    prompt_version="v1",
                )
                db.add(feedback)

                # -- Update user XP --
                user_result = await db.execute(select(User).where(User.id == uid))
                user = user_result.scalar_one_or_none()
                if user:
                    user.xp = (user.xp or 0) + session_score.xp_earned

                scored_users.append(uid_str)

            await db.commit()
            logger.info("Scored session %s for users: %s", session_id, scored_users)
            return scored_users


# Singleton
scoring_engine = ScoringEngine()

"""
Speech Service — STT / TTS / Pronunciation Analysis.

Integrates with Deepgram for real-time Speech-to-Text and provides a TTS
pipeline with ElevenLabs (primary) and OpenAI TTS (fallback). Designed
for low-latency audio streaming over WebSockets.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  Data models                                                  ║
# ╚══════════════════════════════════════════════════════════════╝


@dataclass
class TranscriptionResult:
    text: str
    confidence: float
    words: list[dict]  # [{word, start, end, confidence, punctuated_word}, ...]
    duration_ms: int
    is_final: bool


@dataclass
class PronunciationScore:
    overall: float  # 0-100
    word_scores: list[dict]  # [{word, score, phoneme_issues: [...]}]
    problem_sounds: list[str]
    suggestions: list[str]


# ╔══════════════════════════════════════════════════════════════╗
# ║  Speech-to-Text — Deepgram real-time streaming                ║
# ╚══════════════════════════════════════════════════════════════╝


class DeepgramSTT:
    """
    Streams raw audio bytes to Deepgram's real-time WebSocket API
    and yields TranscriptionResult objects as partial/final results arrive.
    """

    def __init__(self) -> None:
        self._api_key = settings.DEEPGRAM_API_KEY

    async def transcribe_stream(
        self,
        audio_chunks: asyncio.Queue[bytes | None],
        *,
        language: str = "en",
        model: str = "nova-2",
        sample_rate: int = 16000,
        encoding: str = "linear16",
    ):
        """
        Consume audio chunks from a queue, send to Deepgram, and yield results.

        Put `None` into the queue to signal end-of-stream.
        """
        import websockets

        url = (
            f"wss://api.deepgram.com/v1/listen"
            f"?language={language}&model={model}"
            f"&encoding={encoding}&sample_rate={sample_rate}"
            f"&punctuate=true&interim_results=true&utterance_end_ms=1000"
        )
        headers = {"Authorization": f"Token {self._api_key}"}

        async with websockets.connect(url, additional_headers=headers) as ws:
            # Sender task — forward audio chunks to Deepgram
            async def _sender():
                while True:
                    chunk = await audio_chunks.get()
                    if chunk is None:
                        await ws.send(json.dumps({"type": "CloseStream"}))
                        break
                    await ws.send(chunk)

            sender_task = asyncio.create_task(_sender())

            # Receiver — yield transcription results
            try:
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("type") == "Results":
                        channel = msg.get("channel", {})
                        alt = (channel.get("alternatives") or [{}])[0]
                        words = alt.get("words", [])
                        yield TranscriptionResult(
                            text=alt.get("transcript", ""),
                            confidence=alt.get("confidence", 0.0),
                            words=[
                                {
                                    "word": w.get("word", ""),
                                    "start": w.get("start", 0),
                                    "end": w.get("end", 0),
                                    "confidence": w.get("confidence", 0),
                                    "punctuated_word": w.get("punctuated_word", ""),
                                }
                                for w in words
                            ],
                            duration_ms=int(msg.get("duration", 0) * 1000),
                            is_final=msg.get("is_final", False),
                        )
            finally:
                sender_task.cancel()

    async def transcribe_audio(self, audio_bytes: bytes, language: str = "en") -> TranscriptionResult:
        """One-shot transcription for a complete audio file/buffer."""
        import httpx

        url = (
            f"https://api.deepgram.com/v1/listen"
            f"?language={language}&model=nova-2&punctuate=true"
        )
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "audio/wav",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, content=audio_bytes)
            resp.raise_for_status()
            data = resp.json()

        channel = data.get("results", {}).get("channels", [{}])[0]
        alt = (channel.get("alternatives") or [{}])[0]
        words = alt.get("words", [])

        return TranscriptionResult(
            text=alt.get("transcript", ""),
            confidence=alt.get("confidence", 0.0),
            words=[
                {
                    "word": w.get("word", ""),
                    "start": w.get("start", 0),
                    "end": w.get("end", 0),
                    "confidence": w.get("confidence", 0),
                    "punctuated_word": w.get("punctuated_word", ""),
                }
                for w in words
            ],
            duration_ms=int(data.get("metadata", {}).get("duration", 0) * 1000),
            is_final=True,
        )


# ╔══════════════════════════════════════════════════════════════╗
# ║  Text-to-Speech — ElevenLabs (primary) + OpenAI (fallback)   ║
# ╚══════════════════════════════════════════════════════════════╝


class TTSProvider:
    """Base interface for TTS providers."""

    async def synthesize(self, text: str, **kwargs: object) -> bytes:
        raise NotImplementedError


class ElevenLabsTTS(TTSProvider):
    """Generate speech audio using ElevenLabs TTS API."""

    def __init__(self) -> None:
        self._api_key = settings.ELEVENLABS_API_KEY
        self._voice_id = settings.ELEVENLABS_VOICE_ID
        self.name = "elevenlabs"

    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        model_id: str = "eleven_multilingual_v2",
        output_format: str = "mp3_44100_128",
        **kwargs: object,
    ) -> bytes:
        vid = voice_id or self._voice_id
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": f"audio/{output_format.split('_')[0]}",
        }
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.content


class OpenAITTS(TTSProvider):
    """Generate speech audio from text using OpenAI's TTS API."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.name = "openai"

    async def synthesize(
        self,
        text: str,
        voice: str = "alloy",
        model: str = "tts-1",
        response_format: str = "opus",
        **kwargs: object,
    ) -> bytes:
        response = await self.client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format=response_format,
        )
        buf = io.BytesIO()
        async for chunk in response.iter_bytes():
            buf.write(chunk)
        return buf.getvalue()


# ── TTS provider registry ────────────────────────────────────────

_TTS_MAP: dict[str, tuple[str, type[TTSProvider]]] = {
    "elevenlabs": ("ELEVENLABS_API_KEY", ElevenLabsTTS),
    "openai": ("OPENAI_API_KEY", OpenAITTS),
}


class FallbackTTS(TTSProvider):
    """
    Tries TTS providers in priority order. Skips providers with no API key.
    Falls back to the next if one raises an error at runtime.
    """

    def __init__(self) -> None:
        self._providers: list[TTSProvider] = []
        order = [p.strip().lower() for p in settings.TTS_PROVIDER_ORDER.split(",") if p.strip()]

        for name in order:
            entry = _TTS_MAP.get(name)
            if not entry:
                logger.warning("Unknown TTS provider '%s', skipping", name)
                continue
            key_attr, cls = entry
            key_value = getattr(settings, key_attr, "")
            if key_value:
                self._providers.append(cls())
                logger.info("TTS provider '%s' registered (key present)", name)
            else:
                logger.info("TTS provider '%s' skipped (no API key)", name)

        if not self._providers:
            logger.error("No TTS providers configured! Set at least one TTS API key.")

    @property
    def active_provider_name(self) -> str:
        if self._providers:
            return getattr(self._providers[0], "name", "unknown")
        return "none"

    async def synthesize(self, text: str, **kwargs: object) -> bytes:
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                return await provider.synthesize(text, **kwargs)
            except Exception as exc:
                name = getattr(provider, "name", type(provider).__name__)
                logger.warning("TTS provider '%s' failed: %s — trying next", name, exc)
                last_error = exc

        raise RuntimeError(
            f"All TTS providers failed. Last error: {last_error}"
        ) from last_error


# ╔══════════════════════════════════════════════════════════════╗
# ║  Pronunciation Analysis                                       ║
# ╚══════════════════════════════════════════════════════════════╝


class PronunciationAnalyzer:
    """
    Analyze pronunciation quality by comparing per-word confidence scores
    from the STT engine. Words with confidence below threshold are flagged.
    """

    CONFIDENCE_THRESHOLD = 0.75

    def analyze(self, transcription: TranscriptionResult) -> PronunciationScore:
        word_scores = []
        problem_sounds = []

        for w in transcription.words:
            conf = w.get("confidence", 1.0)
            score = round(conf * 100, 1)
            issues = []
            if conf < self.CONFIDENCE_THRESHOLD:
                issues.append("low_confidence")
                problem_sounds.append(w.get("word", ""))
            word_scores.append({
                "word": w.get("word", ""),
                "score": score,
                "phoneme_issues": issues,
            })

        if not word_scores:
            return PronunciationScore(
                overall=0, word_scores=[], problem_sounds=[], suggestions=[]
            )

        avg = sum(ws["score"] for ws in word_scores) / len(word_scores)
        suggestions = []
        if problem_sounds:
            suggestions.append(
                f"Practice these words: {', '.join(problem_sounds[:5])}"
            )
        if avg < 70:
            suggestions.append("Try speaking more slowly and clearly.")
        if avg < 50:
            suggestions.append("Consider repeating the exercise with simpler sentences.")

        return PronunciationScore(
            overall=round(avg, 1),
            word_scores=word_scores,
            problem_sounds=problem_sounds[:10],
            suggestions=suggestions,
        )


# ╔══════════════════════════════════════════════════════════════╗
# ║  Singletons                                                   ║
# ╚══════════════════════════════════════════════════════════════╝

stt_service = DeepgramSTT()
tts_service = FallbackTTS()
pronunciation_analyzer = PronunciationAnalyzer()

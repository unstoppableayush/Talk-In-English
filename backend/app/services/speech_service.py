"""
Speech Service — STT / TTS / Pronunciation Analysis.

Provides a fallback STT chain (Deepgram -> Groq Whisper -> ElevenLabs)
and a fallback TTS chain (ElevenLabs -> Deepgram -> OpenAI) for resilient audio flows.
"""

from __future__ import annotations

import asyncio
import io
import logging
import wave
from dataclasses import dataclass

import httpx
from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.listen.v1.types.listen_v1results import ListenV1Results
from elevenlabs.client import AsyncElevenLabs
from elevenlabs.types import VoiceSettings
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


def _pcm16le_to_wav(
    audio_bytes: bytes,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
) -> bytes:
    """Wrap raw PCM16LE bytes in a WAV container for file-based STT APIs."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit PCM
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_bytes)
    return buffer.getvalue()


# ╔══════════════════════════════════════════════════════════════╗
# ║  Speech-to-Text — provider implementations                    ║
# ╚══════════════════════════════════════════════════════════════╝


class STTProvider:
    """Base interface for STT providers."""

    name = "base"

    async def transcribe_audio(self, audio_bytes: bytes, language: str = "en") -> TranscriptionResult:
        raise NotImplementedError

    async def transcribe_stream(
        self,
        audio_chunks: asyncio.Queue[bytes | None],
        *,
        language: str = "en",
        model: str = "nova-3",
    ):
        """
        Generic stream implementation for non-streaming providers:
        buffer audio until end-of-stream, then emit one final transcript.
        """
        chunks: list[bytes] = []
        while True:
            chunk = await audio_chunks.get()
            if chunk is None:
                break
            chunks.append(chunk)

        if not chunks:
            return

        result = await self.transcribe_audio(b"".join(chunks), language=language)
        yield result


class DeepgramSTT(STTProvider):
    """
    Streams raw audio bytes to Deepgram using the official SDK (v6)
    and yields TranscriptionResult objects as partial/final results arrive.
    """

    def __init__(self) -> None:
        self._api_key = settings.DEEPGRAM_API_KEY
        self.name = "deepgram"

    async def transcribe_stream(
        self,
        audio_chunks: asyncio.Queue[bytes | None],
        *,
        language: str = "en",
        model: str = "nova-2",
    ):
        """
        Consume audio chunks from a queue, send to Deepgram via SDK, yield results.

        Put ``None`` into the queue to signal end-of-stream.
        """
        client = AsyncDeepgramClient(api_key=self._api_key)
        result_queue: asyncio.Queue[TranscriptionResult | None] = asyncio.Queue()
        pending_segments: list[str] = []
        pending_words: list[dict] = []

        def _flush_pending(duration_ms: int) -> None:
            final_text = " ".join(seg for seg in pending_segments if seg).strip()
            if not final_text:
                return
            result_queue.put_nowait(TranscriptionResult(
                text=final_text,
                confidence=0.0,
                words=pending_words.copy(),
                duration_ms=duration_ms,
                is_final=True,
            ))
            pending_segments.clear()
            pending_words.clear()

        async with client.listen.v1.connect(
            model=model,
            language=language,
            encoding="linear16",
            sample_rate="16000",
            channels="1",
            punctuate="true",
            smart_format="true",
            interim_results="true",
            utterance_end_ms="1000",
            vad_events="true",
        ) as connection:

            # --- Event callbacks (push to result_queue) ---
            def _on_message(msg):
                if not isinstance(msg, ListenV1Results):
                    return
                alt = (msg.channel.alternatives or [None])[0]
                if alt is None:
                    return
                transcript = (alt.transcript or "").strip()
                words = [
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "confidence": w.confidence,
                        "punctuated_word": w.punctuated_word or w.word,
                    }
                    for w in (alt.words or [])
                ]
                duration_ms = int(msg.duration * 1000)

                # Deepgram emits multiple final chunks for one utterance.
                # Accumulate them and emit a single final phrase on speech_final.
                if msg.is_final and transcript:
                    pending_segments.append(transcript)
                    pending_words.extend(words)

                if msg.speech_final:
                    _flush_pending(duration_ms)
                    return

                # Send interim text so client can visualize progress.
                if transcript and not msg.is_final:
                    result_queue.put_nowait(TranscriptionResult(
                        text=transcript,
                        confidence=alt.confidence,
                        words=words,
                        duration_ms=duration_ms,
                        is_final=False,
                    ))

            def _on_error(error):
                logger.error("Deepgram SDK error: %s", error)

            connection.on(EventType.MESSAGE, _on_message)
            connection.on(EventType.ERROR, _on_error)

            # --- Sender: forward audio chunks to Deepgram ---
            async def _sender():
                try:
                    while True:
                        try:
                            chunk = await asyncio.wait_for(audio_chunks.get(), timeout=8.0)
                        except asyncio.TimeoutError:
                            await connection.send_keep_alive()
                            continue
                        if chunk is None:
                            await connection.send_finalize()
                            # Give a moment for final results, then signal done
                            await asyncio.sleep(1.0)
                            _flush_pending(0)
                            result_queue.put_nowait(None)
                            return
                        await connection.send_media(chunk)
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    if "ConnectionClosed" in type(exc).__name__:
                        logger.info("Deepgram stream closed by remote side")
                    else:
                        logger.error("Deepgram sender failed", exc_info=True)
                finally:
                    result_queue.put_nowait(None)

            sender_task = asyncio.create_task(_sender())

            # Start the SDK's internal receive loop in the background
            listen_task = asyncio.create_task(connection.start_listening())

            # --- Yield results as they arrive ---
            try:
                while True:
                    item = await result_queue.get()
                    if item is None:
                        break
                    yield item
            finally:
                sender_task.cancel()
                listen_task.cancel()
                try:
                    await connection.send_close_stream()
                except Exception:
                    pass

    async def transcribe_audio(self, audio_bytes: bytes, language: str = "en") -> TranscriptionResult:
        """One-shot transcription for a complete audio file/buffer."""
        wav_bytes = _pcm16le_to_wav(audio_bytes)
        url = (
            f"https://api.deepgram.com/v1/listen"
            f"?language={language}&model=nova-2&punctuate=true"
        )
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "audio/wav",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, content=wav_bytes)
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


class GroqWhisperSTT(STTProvider):
    """One-shot STT through Groq's Whisper-compatible OpenAI API."""

    name = "groq"

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )

    async def transcribe_audio(self, audio_bytes: bytes, language: str = "en") -> TranscriptionResult:
        wav_bytes = _pcm16le_to_wav(audio_bytes)
        response = await self._client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=("audio.wav", wav_bytes, "audio/wav"),
            language=language,
        )

        text = getattr(response, "text", "")
        if not text and isinstance(response, dict):
            text = str(response.get("text", ""))

        return TranscriptionResult(
            text=text,
            confidence=0.0,
            words=[],
            duration_ms=0,
            is_final=True,
        )


class ElevenLabsSTT(STTProvider):
    """One-shot STT using ElevenLabs Speech to Text API."""

    name = "elevenlabs"

    def __init__(self) -> None:
        self._api_key = settings.ELEVENLABS_API_KEY

    async def transcribe_audio(self, audio_bytes: bytes, language: str = "en") -> TranscriptionResult:
        wav_bytes = _pcm16le_to_wav(audio_bytes)
        files = {
            "file": ("audio.wav", wav_bytes, "audio/wav"),
        }
        data = {
            "model_id": "scribe_v1",
            "language_code": language,
        }
        headers = {
            "xi-api-key": self._api_key,
        }

        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                "https://api.elevenlabs.io/v1/speech-to-text",
                headers=headers,
                data=data,
                files=files,
            )
            resp.raise_for_status()
            payload = resp.json()

        text = str(payload.get("text", ""))
        return TranscriptionResult(
            text=text,
            confidence=0.0,
            words=[],
            duration_ms=0,
            is_final=True,
        )


_STT_MAP: dict[str, tuple[str, type[STTProvider]]] = {
    "deepgram": ("DEEPGRAM_API_KEY", DeepgramSTT),
    "groq": ("GROQ_API_KEY", GroqWhisperSTT),
    "elevenlabs": ("ELEVENLABS_API_KEY", ElevenLabsSTT),
}


class FallbackSTT(STTProvider):
    """
    Tries STT providers in priority order and falls back on runtime errors.
    """

    def __init__(self) -> None:
        self._providers: list[STTProvider] = []
        order = [p.strip().lower() for p in settings.STT_PROVIDER_ORDER.split(",") if p.strip()]

        for name in order:
            entry = _STT_MAP.get(name)
            if not entry:
                logger.warning("Unknown STT provider '%s', skipping", name)
                continue
            key_attr, cls = entry
            key_value = getattr(settings, key_attr, "")
            if key_value:
                self._providers.append(cls())
                logger.info("STT provider '%s' registered (key present)", name)
            else:
                logger.info("STT provider '%s' skipped (no API key)", name)

        if not self._providers:
            logger.error("No STT providers configured! Set at least one STT API key.")

    async def transcribe_audio(self, audio_bytes: bytes, language: str = "en") -> TranscriptionResult:
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                return await provider.transcribe_audio(audio_bytes, language=language)
            except Exception as exc:
                logger.warning(
                    "STT provider '%s' failed for one-shot transcription: %s — trying next",
                    provider.name,
                    exc,
                )
                last_error = exc

        raise RuntimeError(
            f"All STT providers failed. Last error: {last_error}"
        ) from last_error

    async def transcribe_stream(
        self,
        audio_chunks: asyncio.Queue[bytes | None],
        *,
        language: str = "en",
        model: str = "nova-2",
    ):
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                async for result in provider.transcribe_stream(
                    audio_chunks,
                    language=language,
                    model=model,
                ):
                    yield result
                return
            except Exception as exc:
                logger.warning(
                    "STT provider '%s' failed for streaming: %s — trying next",
                    provider.name,
                    exc,
                )
                last_error = exc

        raise RuntimeError(
            f"All STT providers failed. Last error: {last_error}"
        ) from last_error


# ╔══════════════════════════════════════════════════════════════╗
# ║  Text-to-Speech — fallback provider chain                     ║
# ╚══════════════════════════════════════════════════════════════╝


class TTSProvider:
    """Base interface for TTS providers."""

    async def synthesize(self, text: str, **kwargs: object) -> bytes:
        raise NotImplementedError


class ElevenLabsTTS(TTSProvider):
    """Generate speech audio using the official ElevenLabs SDK."""

    def __init__(self) -> None:
        self._client = AsyncElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
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
        audio_iter = self._client.text_to_speech.convert(
            voice_id=voice_id or self._voice_id,
            text=text,
            model_id=model_id,
            output_format=output_format,
            voice_settings=VoiceSettings(
                stability=0.5,
                similarity_boost=0.75,
            ),
        )
        buf = io.BytesIO()
        async for chunk in audio_iter:
            buf.write(chunk)
        return buf.getvalue()


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


class DeepgramTTS(TTSProvider):
    """Generate speech audio from text using Deepgram Aura TTS."""

    def __init__(self) -> None:
        self._api_key = settings.DEEPGRAM_API_KEY
        self.name = "deepgram"

    async def synthesize(
        self,
        text: str,
        model: str | None = None,
        **kwargs: object,
    ) -> bytes:
        selected_model = model or settings.DEEPGRAM_TTS_MODEL
        url = f"https://api.deepgram.com/v1/speak?model={selected_model}"
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {"text": text}

        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.content


# ── TTS provider registry ────────────────────────────────────────

_TTS_MAP: dict[str, tuple[str, type[TTSProvider]]] = {
    "elevenlabs": ("ELEVENLABS_API_KEY", ElevenLabsTTS),
    "deepgram": ("DEEPGRAM_API_KEY", DeepgramTTS),
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

stt_service = FallbackSTT()
tts_service = FallbackTTS()
pronunciation_analyzer = PronunciationAnalyzer()

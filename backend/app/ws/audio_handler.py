"""
Audio WebSocket handler — real-time STT/TTS streaming.

Client sends binary audio frames → server forwards to Deepgram STT →
transcription results are broadcast to the session.
Optionally, the server can synthesize AI replies via TTS and send audio back.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.database import async_session
from app.core.security import decode_token
from app.models.message import Message
from app.services.speech_service import (
    pronunciation_analyzer,
    stt_service,
    tts_service,
)
from app.ws.connection_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/audio/{session_id}")
async def websocket_audio(
    ws: WebSocket,
    session_id: str,
    token: str = Query(...),
    language: str = Query(default="en"),
):
    """
    Audio streaming WebSocket.

    Client → Server: binary audio frames (16kHz, 16-bit PCM)
    Server → Client: JSON transcription events + optional binary TTS audio
    """
    # --- Authenticate ---
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await ws.close(code=4001, reason="Invalid token")
        return

    user_id = payload["sub"]
    await ws.accept()

    # Queue for feeding audio chunks to STT
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    # Task that consumes STT results and broadcasts them
    async def _stt_consumer():
        try:
            async for result in stt_service.transcribe_stream(
                audio_queue, language=language
            ):
                # Send transcription to client
                await ws.send_json({
                    "event": "transcription.result",
                    "data": {
                        "text": result.text,
                        "confidence": result.confidence,
                        "is_final": result.is_final,
                        "duration_ms": result.duration_ms,
                        "words": result.words,
                    },
                })

                # On final utterance, persist as message and run pronunciation
                if result.is_final and result.text.strip():
                    msg_id = str(uuid.uuid4())
                    now = datetime.now(timezone.utc).isoformat()

                    async with async_session() as db:
                        message = Message(
                            id=msg_id,
                            session_id=session_id,
                            sender_id=user_id,
                            sender_type="user",
                            content=result.text,
                            message_type="audio_transcription",
                            word_count=len(result.text.split()),
                            audio_duration_ms=result.duration_ms,
                            stt_confidence=result.confidence,
                        )
                        db.add(message)
                        await db.commit()

                    # Broadcast to session
                    await manager.broadcast_to_session(session_id, {
                        "event": "message.received",
                        "data": {
                            "id": msg_id,
                            "sender_id": user_id,
                            "sender_type": "user",
                            "content": result.text,
                            "message_type": "audio_transcription",
                            "created_at": now,
                        },
                    })

                    # Pronunciation analysis
                    pron = pronunciation_analyzer.analyze(result)
                    await ws.send_json({
                        "event": "pronunciation.result",
                        "data": {
                            "overall": pron.overall,
                            "word_scores": pron.word_scores,
                            "problem_sounds": pron.problem_sounds,
                            "suggestions": pron.suggestions,
                        },
                    })
        except Exception:
            logger.debug("STT consumer error for session %s", session_id, exc_info=True)

    stt_task = asyncio.create_task(_stt_consumer())

    # --- Audio receive loop ---
    try:
        while True:
            data = await ws.receive()

            if "bytes" in data and data["bytes"]:
                # Binary frame — forward to STT queue
                await audio_queue.put(data["bytes"])

            elif "text" in data and data["text"]:
                # JSON control message
                try:
                    msg = json.loads(data["text"])
                except json.JSONDecodeError:
                    continue

                event = msg.get("event")

                if event == "audio.tts.request":
                    # Client requests TTS for given text
                    text = msg.get("data", {}).get("text", "")
                    voice = msg.get("data", {}).get("voice", "alloy")
                    if text:
                        audio_bytes = await tts_service.synthesize(text, voice=voice)
                        # Send TTS metadata then binary audio
                        await ws.send_json({
                            "event": "audio.tts.start",
                            "data": {"text": text, "voice": voice},
                        })
                        await ws.send_bytes(audio_bytes)
                        await ws.send_json({
                            "event": "audio.tts.end",
                            "data": {},
                        })

                elif event == "system.ping":
                    await ws.send_json({"event": "system.pong", "data": {}})

    except WebSocketDisconnect:
        pass
    finally:
        # Signal STT stream to close
        await audio_queue.put(None)
        stt_task.cancel()

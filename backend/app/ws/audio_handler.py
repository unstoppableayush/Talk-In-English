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
from sqlalchemy import select

from app.core.database import async_session
from app.core.security import decode_token
from app.models.message import Message
from app.models.session import Session
from app.models.user import User
from app.services.ai_service import conversation_manager
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

    # --- Fetch session info & user display name ---
    async with async_session() as db:
        session_result = await db.execute(select(Session).where(Session.id == session_id))
        session = session_result.scalar_one_or_none()
        if not session or session.status not in ("waiting", "active"):
            await ws.close(code=4004, reason="Session not found or not active")
            return

        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            await ws.close(code=4001, reason="User not found")
            return

        display_name = user.display_name
        session_mode = session.mode
        session_topic = session.topic or "General conversation"
        session_config = session.config or {}
        target_lang = session_config.get("language", "English")
        difficulty = session_config.get("difficulty", "intermediate")

    await ws.accept()

    # --- Initialize AI context for 1-on-1 mode ---
    if session_mode == "ai_1on1":
        conversation_manager.get_or_create_context(
            session_id, mode=session_mode, topic=session_topic,
            difficulty=difficulty, target_language=target_lang,
        )

    # Queue for feeding audio chunks to STT
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    stt_task: asyncio.Task | None = None

    # Task that consumes STT results and broadcasts them
    async def _stt_consumer():
        try:
            async for result in stt_service.transcribe_stream(
                audio_queue, language=language
            ):
                # Send transcription to client
                try:
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
                except Exception:
                    break  # client disconnected

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

                    # Broadcast user message to session
                    await manager.broadcast_to_session(session_id, {
                        "event": "message.received",
                        "data": {
                            "id": msg_id,
                            "sender_id": user_id,
                            "sender_name": display_name,
                            "sender_type": "user",
                            "content": result.text,
                            "message_type": "audio_transcription",
                            "created_at": now,
                        },
                    })

                    # Pronunciation analysis
                    pron = pronunciation_analyzer.analyze(result)
                    try:
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
                        break

                    # Generate AI reply for 1-on-1 mode
                    if session_mode == "ai_1on1":
                        try:
                            ai_reply = await conversation_manager.get_ai_reply(
                                session_id, result.text, display_name,
                            )
                            if ai_reply:
                                ai_msg_id = str(uuid.uuid4())
                                ai_now = datetime.now(timezone.utc).isoformat()

                                async with async_session() as db:
                                    ai_message = Message(
                                        id=ai_msg_id,
                                        session_id=session_id,
                                        sender_id=None,
                                        sender_type="ai",
                                        content=ai_reply,
                                        message_type="text",
                                        word_count=len(ai_reply.split()),
                                    )
                                    db.add(ai_message)
                                    await db.commit()

                                await manager.broadcast_to_session(session_id, {
                                    "event": "message.received",
                                    "data": {
                                        "id": ai_msg_id,
                                        "sender_id": "ai",
                                        "sender_name": "AI Practice Partner",
                                        "sender_type": "ai",
                                        "content": ai_reply,
                                        "message_type": "text",
                                        "created_at": ai_now,
                                    },
                                })
                        except Exception:
                            logger.exception(
                                "Error generating AI reply via audio in session=%s",
                                session_id,
                            )
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.error("STT consumer failed for session %s", session_id, exc_info=True)

    def _ensure_stt_running():
        """Start the STT consumer lazily on the first audio chunk."""
        nonlocal stt_task
        if stt_task is None or stt_task.done():
            stt_task = asyncio.create_task(_stt_consumer())

    # --- Audio receive loop ---
    try:
        while True:
            data = await ws.receive()

            if "bytes" in data and data["bytes"]:
                # Binary frame — start STT on first chunk, then forward
                _ensure_stt_running()
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
                        try:
                            audio_bytes = await tts_service.synthesize(text, voice=voice)
                            await ws.send_json({
                                "event": "audio.tts.start",
                                "data": {"text": text, "voice": voice},
                            })
                            await ws.send_bytes(audio_bytes)
                            await ws.send_json({
                                "event": "audio.tts.end",
                                "data": {},
                            })
                        except Exception:
                            logger.exception("TTS failed in session=%s", session_id)

                elif event == "system.ping":
                    await ws.send_json({"event": "system.pong", "data": {}})

    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        # Signal STT stream to close
        await audio_queue.put(None)
        if stt_task and not stt_task.done():
            stt_task.cancel()

"""
Roleplay WebSocket handler — real-time conversation streaming.

Protocol:
  1. Client connects to /ws/roleplay/{session_id}?token=<jwt>
  2. Server sends {"event": "roleplay.connected", "data": {...}}
  3. Client sends {"event": "roleplay.message", "data": {"content": "..."}}
  4. Server responds with {"event": "roleplay.ai_reply", "data": {"content": "...", ...}}
  5. Client sends {"event": "roleplay.end"} to end session
  6. Server sends {"event": "roleplay.ended", "data": {...}}
"""

import json
import logging
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.database import async_session
from app.core.security import decode_token
from app.models.roleplay import RoleplayMessage, RoleplayScenario, RoleplaySession
from app.models.user import User
from app.services.roleplay_service import roleplay_engine
from app.services.speech_service import stt_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/roleplay-audio/{session_id}")
async def ws_roleplay_audio(
    ws: WebSocket,
    session_id: str,
    token: str = Query(...),
    language: str = Query(default="en"),
):
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await ws.close(code=4001, reason="Invalid token")
        return

    user_id = payload["sub"]

    async with async_session() as db:
        result = await db.execute(
            select(RoleplaySession).where(
                RoleplaySession.id == session_id,
                RoleplaySession.user_id == user_id,
                RoleplaySession.status == "active",
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            await ws.close(code=4004, reason="Session not found or not active")
            return

    await ws.accept()

    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    stt_task: asyncio.Task | None = None

    async def _stt_consumer():
        try:
            async for result in stt_service.transcribe_stream(audio_queue, language=language):
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
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Roleplay STT consumer failed for session=%s", session_id)

    def _ensure_stt_running() -> None:
        nonlocal stt_task
        if stt_task is None or stt_task.done():
            stt_task = asyncio.create_task(_stt_consumer())

    try:
        while True:
            data = await ws.receive()

            if "bytes" in data and data["bytes"]:
                _ensure_stt_running()
                await audio_queue.put(data["bytes"])
            elif "text" in data and data["text"]:
                try:
                    msg = json.loads(data["text"])
                except json.JSONDecodeError:
                    continue
                if msg.get("event") == "audio.stt.flush":
                    await audio_queue.put(None)
                elif msg.get("event") == "system.ping":
                    await ws.send_json({"event": "system.pong", "data": {}})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await audio_queue.put(None)
        if stt_task and not stt_task.done():
            stt_task.cancel()


@router.websocket("/roleplay/{session_id}")
async def ws_roleplay(
    ws: WebSocket,
    session_id: str,
    token: str = Query(...),
):
    # ── Authenticate ──
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await ws.close(code=4001, reason="Invalid token")
        return

    user_id = payload["sub"]

    # ── Validate session ──
    async with async_session() as db:
        result = await db.execute(
            select(RoleplaySession).where(
                RoleplaySession.id == session_id,
                RoleplaySession.user_id == user_id,
                RoleplaySession.status == "active",
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            await ws.close(code=4004, reason="Session not found or not active")
            return

        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            await ws.close(code=4001, reason="User not found")
            return

        display_name = user.display_name

        # Load scenario info
        topic = session.custom_topic or "General conversation"
        scenario_desc = "General conversation"
        ai_role = "Conversational partner"
        user_role = "Participant"

        if session.scenario_id:
            sc_result = await db.execute(
                select(RoleplayScenario).where(RoleplayScenario.id == session.scenario_id)
            )
            scenario = sc_result.scalar_one_or_none()
            if scenario:
                topic = scenario.title
                scenario_desc = scenario.description or scenario.title
                ai_role = scenario.ai_role
                user_role = scenario.user_role

        # Load existing messages for context recovery
        msg_result = await db.execute(
            select(RoleplayMessage)
            .where(RoleplayMessage.session_id == session.id)
            .order_by(RoleplayMessage.created_at)
        )
        existing_msgs = msg_result.scalars().all()

    # ── Ensure AI context is initialized ──
    roleplay_engine.create_context(
        session_id=session_id,
        topic=topic,
        scenario_description=scenario_desc,
        ai_role=ai_role,
        user_role=user_role,
        difficulty=session.difficulty,
    )
    # Replay existing history into context
    for msg in existing_msgs:
        role = "user" if msg.sender == "user" else "assistant"
        ctx = roleplay_engine._contexts.get(session_id)
        if ctx:
            ctx.history.append({"role": role, "content": msg.content})

    await ws.accept()

    # ── Send connected event ──
    await ws.send_json({
        "event": "roleplay.connected",
        "data": {
            "session_id": session_id,
            "topic": topic,
            "ai_role": ai_role,
            "user_role": user_role,
            "difficulty": session.difficulty,
            "message_count": len(existing_msgs),
        },
    })

    # ── Message loop ──
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"event": "error", "data": {"message": "Invalid JSON"}})
                continue

            event = msg.get("event", "")
            data = msg.get("data", {})

            if event == "roleplay.message":
                content = data.get("content", "").strip()
                if not content:
                    continue

                try:
                    # Persist user message
                    async with async_session() as db:
                        user_msg = RoleplayMessage(
                            session_id=session_id, sender="user", content=content
                        )
                        db.add(user_msg)
                        await db.commit()
                        await db.refresh(user_msg)

                    # Generate AI reply
                    ai_text = await roleplay_engine.generate_reply(session_id, content)

                    # Persist AI message
                    async with async_session() as db:
                        ai_msg = RoleplayMessage(
                            session_id=session_id, sender="ai", content=ai_text
                        )
                        db.add(ai_msg)
                        await db.commit()
                        await db.refresh(ai_msg)

                    await ws.send_json({
                        "event": "roleplay.ai_reply",
                        "data": {
                            "id": str(ai_msg.id),
                            "content": ai_text,
                            "created_at": ai_msg.created_at.isoformat(),
                        },
                    })
                except Exception:
                    logger.exception("Error handling roleplay message session=%s", session_id)
                    await ws.send_json({"event": "error", "data": {"message": "Failed to process message"}})

            elif event == "roleplay.end":
                # End session
                try:
                    async with async_session() as db:
                        result = await db.execute(
                            select(RoleplaySession).where(RoleplaySession.id == session_id)
                        )
                        sess = result.scalar_one_or_none()
                        if sess and sess.status == "active":
                            now = datetime.now(timezone.utc)
                            sess.status = "completed"
                            sess.ended_at = now
                            if sess.started_at:
                                sess.duration_sec = int((now - sess.started_at).total_seconds())
                            await db.commit()

                    roleplay_engine.remove_context(session_id)

                    await ws.send_json({
                        "event": "roleplay.ended",
                        "data": {"session_id": session_id, "status": "completed"},
                    })

                    # Trigger evaluation (fire and forget via import)
                    import asyncio
                    asyncio.create_task(roleplay_engine.evaluate_session(session_id))
                except Exception:
                    logger.exception("Error ending roleplay session=%s via WS", session_id)
                break

            elif event == "system.ping":
                await ws.send_json({"event": "system.pong", "data": {}})

    except WebSocketDisconnect:
        pass
    finally:
        roleplay_engine.remove_context(session_id)

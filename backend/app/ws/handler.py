import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session
from app.core.security import decode_token
from app.models.message import Message
from app.models.session import Session, RoomParticipant
from app.models.user import User
from app.services.ai_service import conversation_manager, moderation_service, scoring_engine
from app.ws.connection_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/session/{session_id}")
async def websocket_session(
    ws: WebSocket,
    session_id: str,
    token: str = Query(...),
    role: str = Query(default="speaker"),
):
    # --- Authenticate ---
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await ws.close(code=4001, reason="Invalid token")
        return

    user_id = payload["sub"]

    # --- Validate session exists ---
    async with async_session() as db:
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if not session or session.status not in ("waiting", "active"):
            await ws.close(code=4004, reason="Session not found or not active")
            return

        # Get user info
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            await ws.close(code=4001, reason="User not found")
            return

        display_name = user.display_name

    # --- Connect ---
    if role == "speaker":
        info = manager.get_session_info(session_id)
        if info["speaker_count"] >= settings.MAX_SPEAKERS_PER_ROOM:
            await ws.accept()
            await ws.send_json({
                "event": "connection.rejected",
                "data": {"reason": "SESSION_FULL", "message": "All speaker slots are taken."},
            })
            await ws.close()
            return
        await manager.connect_speaker(session_id, user_id, ws)
    else:
        await manager.connect_listener(session_id, ws, user_id=user_id)

    # --- Send session state ---
    info = manager.get_session_info(session_id)
    await ws.send_json({
        "event": "connection.accepted",
        "data": {
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "mode": session.mode,
        },
    })
    await ws.send_json({
        "event": "session.state",
        "data": {
            "session_id": session_id,
            "mode": session.mode,
            "status": session.status,
            "speaker_count": info["speaker_count"],
            "listener_count": info["listener_count"],
            "speakers": info["speakers"],
        },
    })

    # --- Notify others ---
    if role == "speaker":
        await manager.broadcast_to_session(session_id, {
            "event": "participant.joined",
            "data": {
                "user_id": user_id,
                "display_name": display_name,
                "role": "speaker",
                "speaker_count": info["speaker_count"],
                "listener_count": info["listener_count"],
            },
        })

    # --- Initialize AI context for applicable modes ---
    session_mode = session.mode
    session_topic = session.topic or "General conversation"
    session_config = session.config or {}
    target_lang = session_config.get("language", "English")
    difficulty = session_config.get("difficulty", "intermediate")

    if session_mode == "ai_1on1":
        conversation_manager.get_or_create_context(
            session_id, mode=session_mode, topic=session_topic,
            difficulty=difficulty, target_language=target_lang,
        )

    # --- Message loop ---
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({
                    "event": "connection.error",
                    "data": {"code": "INVALID_JSON", "message": "Message must be valid JSON"},
                })
                continue

            event = data.get("event")
            event_data = data.get("data", {})

            # ── Text message (speakers only) ──────────────────
            if event == "message.send" and role == "speaker":
                await _handle_message(
                    session_id, user_id, display_name, event_data,
                    mode=session_mode, topic=session_topic,
                )

            # ── Audio activity flags ──────────────────────────
            elif event == "audio.speaking.start":
                await manager.broadcast_to_session(session_id, {
                    "event": "audio.speaker.active",
                    "data": {"user_id": user_id, "display_name": display_name, "is_speaking": True},
                })
            elif event == "audio.speaking.stop":
                await manager.broadcast_to_session(session_id, {
                    "event": "audio.speaker.active",
                    "data": {"user_id": user_id, "display_name": display_name, "is_speaking": False},
                })

            # ── Raise hand (listeners raise, toggle) ──────────
            elif event == "hand.raise":
                new_state = await _handle_raise_hand(session_id, user_id)
                if new_state is not None:
                    await manager.broadcast_to_session(session_id, {
                        "event": "hand.raised",
                        "data": {
                            "user_id": user_id,
                            "display_name": display_name,
                            "hand_raised": new_state,
                        },
                    })

            # ── Promote listener → speaker (owner/moderator) ──
            elif event == "participant.promote" and role == "speaker":
                target_user_id = event_data.get("user_id")
                if target_user_id:
                    success = await _handle_promote(session_id, user_id, target_user_id)
                    if success:
                        # Move the WebSocket from listener list to speaker map
                        manager.promote_listener_to_speaker(session_id, target_user_id)
                        info = manager.get_session_info(session_id)
                        await manager.broadcast_to_session(session_id, {
                            "event": "participant.promoted",
                            "data": {
                                "user_id": target_user_id,
                                "new_role": "speaker",
                                "promoted_by": user_id,
                                "speaker_count": info["speaker_count"],
                                "listener_count": info["listener_count"],
                            },
                        })
                    else:
                        await ws.send_json({
                            "event": "connection.error",
                            "data": {"code": "PROMOTE_FAILED", "message": "Cannot promote user."},
                        })

            # ── Ping / Pong ───────────────────────────────────
            elif event == "system.ping":
                await ws.send_json({"event": "system.pong", "data": {}})

    except WebSocketDisconnect:
        pass
    finally:
        # Clean up AI context on disconnect
        if session_mode == "ai_1on1":
            conversation_manager.remove_context(session_id)
        elif session_mode == "public_room":
            moderation_service.clear(session_id)

        if role == "speaker":
            manager.disconnect_speaker(session_id, user_id)
            info = manager.get_session_info(session_id)
            await manager.broadcast_to_session(session_id, {
                "event": "participant.left",
                "data": {
                    "user_id": user_id,
                    "display_name": display_name,
                    "speaker_count": info["speaker_count"],
                    "listener_count": info["listener_count"],
                },
            })
        else:
            manager.disconnect_listener(session_id, ws, user_id=user_id)


# ── Internal handlers ─────────────────────────────────────────

async def _handle_message(
    session_id: str,
    user_id: str,
    display_name: str,
    data: dict,
    mode: str = "ai_1on1",
    topic: str = "General conversation",
) -> None:
    """Persist a message, broadcast it, and trigger mode-specific AI logic."""
    content = data.get("content", "").strip()
    if not content:
        return

    msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    try:
        # Persist user message
        async with async_session() as db:
            message = Message(
                id=msg_id,
                session_id=session_id,
                sender_id=user_id,
                sender_type="user",
                content=content,
                message_type=data.get("message_type", "text"),
                word_count=len(content.split()),
            )
            db.add(message)
            await db.commit()
    except Exception:
        logger.exception("Error persisting message in session=%s", session_id)

    # Broadcast user message
    await manager.broadcast_to_session(session_id, {
        "event": "message.received",
        "data": {
            "id": msg_id,
            "sender_id": user_id,
            "sender_name": display_name,
            "sender_type": "user",
            "content": content,
            "message_type": data.get("message_type", "text"),
            "created_at": now,
        },
    })

    # ── Mode 1: AI 1-on-1 — generate AI reply ────────────────
    if mode == "ai_1on1":
        try:
            ai_reply = await conversation_manager.get_ai_reply(session_id, content, display_name)
            if ai_reply:
                ai_msg_id = str(uuid.uuid4())
                ai_now = datetime.now(timezone.utc).isoformat()

                # Persist AI message
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

                # Send AI reply to user
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
            logger.exception("Error generating AI reply in session=%s", session_id)

    # ── Mode 2: Peer 1-on-1 — silent monitoring (no AI messages) ──
    # Messages are stored above; AI analysis happens at session end via scoring_engine.

    # ── Mode 3: Public room — AI moderation ───────────────────
    elif mode == "public_room":
        try:
            moderation_service.add_message(session_id, display_name, content)

            action = await moderation_service.check_moderation(session_id, topic)
            if action:
                mod_msg_id = str(uuid.uuid4())
                mod_now = datetime.now(timezone.utc).isoformat()

                # Persist moderation message
                async with async_session() as db:
                    mod_message = Message(
                        id=mod_msg_id,
                        session_id=session_id,
                        sender_id=None,
                        sender_type="ai",
                        content=action.message,
                        message_type="moderation",
                        word_count=len(action.message.split()),
                    )
                    db.add(mod_message)
                    await db.commit()

                # Broadcast moderation message
                await manager.broadcast_to_session(session_id, {
                    "event": "moderation.action",
                    "data": {
                        "id": mod_msg_id,
                        "action": action.action,
                        "message": action.message,
                        "target_user": action.target_user,
                        "created_at": mod_now,
                    },
                })
        except Exception:
            logger.exception("Error in moderation for session=%s", session_id)


async def _handle_raise_hand(session_id: str, user_id: str) -> bool | None:
    """Toggle hand_raised in DB. Returns the new state, or None on failure."""
    try:
        async with async_session() as db:
            result = await db.execute(
                select(RoomParticipant).where(
                    RoomParticipant.session_id == session_id,
                    RoomParticipant.user_id == user_id,
                    RoomParticipant.is_active.is_(True),
                )
            )
            participant = result.scalar_one_or_none()
            if not participant:
                return None

            participant.hand_raised = not participant.hand_raised
            new_state = participant.hand_raised
            await db.commit()
        return new_state
    except Exception:
        logger.exception("Error handling raise hand session=%s user=%s", session_id, user_id)
        return None


async def _handle_promote(session_id: str, promoter_id: str, target_user_id: str) -> bool:
    """Promote a listener to speaker in the DB. Returns True on success."""
    try:
        async with async_session() as db:
            # Verify promoter is the session creator or an admin
            session_result = await db.execute(select(Session).where(Session.id == session_id))
            session = session_result.scalar_one_or_none()
            if not session:
                return False

            promoter_result = await db.execute(select(User).where(User.id == promoter_id))
            promoter = promoter_result.scalar_one_or_none()
            if not promoter:
                return False

            if session.created_by != promoter.id and promoter.role not in ("admin", "moderator"):
                return False

            # Find the target participant
            target_result = await db.execute(
                select(RoomParticipant).where(
                    RoomParticipant.session_id == session_id,
                    RoomParticipant.user_id == target_user_id,
                    RoomParticipant.is_active.is_(True),
                )
            )
            target = target_result.scalar_one_or_none()
            if not target or target.role == "speaker":
                return False

            target.role = "speaker"
            target.hand_raised = False
            await db.commit()

        return True
    except Exception:
        logger.exception("Error promoting user=%s in session=%s", target_user_id, session_id)
        return False

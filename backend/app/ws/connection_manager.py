from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class SessionConnections:
    """Tracks WebSocket connections for a single session."""

    speakers: dict[str, WebSocket] = field(default_factory=dict)  # user_id → ws
    listeners: dict[str, WebSocket] = field(default_factory=dict)  # user_id → ws (keyed for promote)
    anonymous_listeners: list[WebSocket] = field(default_factory=list)  # no user_id (untracked)

    @property
    def speaker_count(self) -> int:
        return len(self.speakers)

    @property
    def listener_count(self) -> int:
        return len(self.listeners) + len(self.anonymous_listeners)


class ConnectionManager:
    """
    Manages WebSocket connections across all active sessions.

    For single-process mode this works in-memory.
    In production with multiple workers, call `enable_redis()` to add
    Redis pub/sub fan-out so broadcasts reach every pod.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionConnections] = {}
        self._redis = None
        self._pubsub_task: asyncio.Task | None = None
        self._instance_id = uuid4().hex

    # ── Redis pub/sub (optional, for horizontal scaling) ──────

    async def enable_redis(self, redis_url: str) -> None:
        """Connect to Redis and subscribe to the broadcast channel."""
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(redis_url, decode_responses=True)
            pubsub = self._redis.pubsub()
            await pubsub.subscribe("ws:broadcast")
            self._pubsub_task = asyncio.create_task(self._redis_listener(pubsub))
            logger.info("Redis pub/sub enabled for WebSocket scaling")
        except Exception:
            logger.warning("Redis unavailable — falling back to in-memory broadcast", exc_info=True)
            self._redis = None

    async def _redis_listener(self, pubsub) -> None:
        """Background coroutine that relays messages from Redis to local sessions."""
        try:
            async for raw_msg in pubsub.listen():
                if raw_msg["type"] != "message":
                    continue
                try:
                    envelope = json.loads(raw_msg["data"])
                    if envelope.get("source") == self._instance_id:
                        continue
                    session_id = envelope["session_id"]
                    message = envelope["payload"]
                    await self._local_broadcast(session_id, message)
                except Exception:
                    logger.debug("Failed to relay Redis message", exc_info=True)
        except asyncio.CancelledError:
            pass

    async def _publish(self, session_id: str, message: dict) -> None:
        """Publish a message to Redis so other pods can relay it."""
        if self._redis:
            envelope = json.dumps(
                {
                    "source": self._instance_id,
                    "session_id": session_id,
                    "payload": message,
                }
            )
            try:
                await self._redis.publish("ws:broadcast", envelope)
            except Exception:
                logger.warning(
                    "Redis publish failed — continuing with local WebSocket broadcast only",
                    exc_info=True,
                )
                self._redis = None

    # ── Connection lifecycle ──────────────────────────────────

    def _get_or_create(self, session_id: str) -> SessionConnections:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionConnections()
        return self._sessions[session_id]

    async def connect_speaker(self, session_id: str, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        conns = self._get_or_create(session_id)
        conns.speakers[user_id] = ws

    async def connect_listener(self, session_id: str, ws: WebSocket, user_id: str | None = None) -> None:
        await ws.accept()
        conns = self._get_or_create(session_id)
        if user_id:
            conns.listeners[user_id] = ws
        else:
            conns.anonymous_listeners.append(ws)

    def disconnect_speaker(self, session_id: str, user_id: str) -> None:
        conns = self._sessions.get(session_id)
        if conns:
            conns.speakers.pop(user_id, None)
            self._cleanup_if_empty(session_id)

    def disconnect_listener(self, session_id: str, ws: WebSocket, user_id: str | None = None) -> None:
        conns = self._sessions.get(session_id)
        if not conns:
            return
        if user_id and user_id in conns.listeners:
            conns.listeners.pop(user_id, None)
        else:
            try:
                conns.anonymous_listeners.remove(ws)
            except ValueError:
                pass
        self._cleanup_if_empty(session_id)

    def promote_listener_to_speaker(self, session_id: str, user_id: str) -> bool:
        """Move a tracked listener's WebSocket to the speakers dict."""
        conns = self._sessions.get(session_id)
        if not conns or user_id not in conns.listeners:
            return False
        ws = conns.listeners.pop(user_id)
        conns.speakers[user_id] = ws
        return True

    def _cleanup_if_empty(self, session_id: str) -> None:
        conns = self._sessions.get(session_id)
        if conns and conns.speaker_count == 0 and conns.listener_count == 0:
            del self._sessions[session_id]

    # ── Broadcasting ──────────────────────────────────────────

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        """Send to all local connections and publish to Redis for other pods."""
        await self._local_broadcast(session_id, message)
        await self._publish(session_id, message)

    async def _local_broadcast(self, session_id: str, message: dict) -> None:
        """Send a message to all speakers and listeners on THIS process."""
        conns = self._sessions.get(session_id)
        if not conns:
            return
        tasks = []
        for ws in conns.speakers.values():
            tasks.append(self._safe_send(ws, message))
        for ws in conns.listeners.values():
            tasks.append(self._safe_send(ws, message))
        for ws in conns.anonymous_listeners:
            tasks.append(self._safe_send(ws, message))
        if tasks:
            await asyncio.gather(*tasks)

    async def send_to_speaker(self, session_id: str, user_id: str, message: dict) -> None:
        """Send a message to a specific speaker."""
        conns = self._sessions.get(session_id)
        if conns and user_id in conns.speakers:
            await self._safe_send(conns.speakers[user_id], message)

    async def broadcast_to_speakers(self, session_id: str, message: dict) -> None:
        """Send a message to all speakers only (not listeners)."""
        conns = self._sessions.get(session_id)
        if not conns:
            return
        tasks = [self._safe_send(ws, message) for ws in conns.speakers.values()]
        if tasks:
            await asyncio.gather(*tasks)

    def get_session_info(self, session_id: str) -> dict:
        conns = self._sessions.get(session_id)
        if not conns:
            return {"speaker_count": 0, "listener_count": 0, "speakers": []}
        return {
            "speaker_count": conns.speaker_count,
            "listener_count": conns.listener_count,
            "speakers": list(conns.speakers.keys()),
        }

    @staticmethod
    async def _safe_send(ws: WebSocket, message: dict) -> None:
        try:
            await ws.send_json(message)
        except Exception:
            logger.debug("Failed to send message to WebSocket", exc_info=True)


# Singleton instance
manager = ConnectionManager()

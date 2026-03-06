# WebSocket Event Design

## Connection

### Endpoint
```
wss://api.speakingapp.com/ws/session/{session_id}?token={jwt_access_token}&role={speaker|listener}
```

### Connection Lifecycle
```
Client                                          Server
  │                                                │
  │──── WS Upgrade + JWT ─────────────────────────►│
  │                                                │── Validate JWT
  │                                                │── Check session exists
  │                                                │── Check role capacity
  │◄─── connection.accepted ──────────────────────│
  │                                                │
  │◄─── session.state (full current state) ───────│
  │                                                │
  │     ... bidirectional events ...                │
  │                                                │
  │──── connection.close ─────────────────────────►│
  │◄─── connection.closed ────────────────────────│
```

---

## Message Format

All WebSocket messages are JSON with this envelope:

```json
{
    "event": "event.name",
    "data": { ... },
    "timestamp": "2026-03-06T10:00:00.000Z",
    "id": "msg-uuid"
}
```

**Client → Server** messages include:
```json
{
    "event": "event.name",
    "data": { ... }
}
```

**Server → Client** messages include:
```json
{
    "event": "event.name",
    "data": { ... },
    "timestamp": "2026-03-06T10:00:00.000Z",
    "id": "msg-uuid"
}
```

---

## Event Categories

### 1. Connection Events

#### `connection.accepted` (Server → Client)
Sent after successful authentication and join.
```json
{
    "event": "connection.accepted",
    "data": {
        "session_id": "uuid",
        "user_id": "uuid",
        "role": "speaker",
        "mode": "public_room"
    }
}
```

#### `connection.rejected` (Server → Client)
Sent when connection is denied.
```json
{
    "event": "connection.rejected",
    "data": {
        "reason": "SESSION_FULL",
        "message": "All speaker slots are taken. You can join as a listener."
    }
}
```

#### `connection.error` (Server → Client)
Sent on protocol errors.
```json
{
    "event": "connection.error",
    "data": {
        "code": "INVALID_MESSAGE",
        "message": "Unrecognized event type"
    }
}
```

---

### 2. Session State Events

#### `session.state` (Server → Client)
Full session state snapshot, sent on connect.
```json
{
    "event": "session.state",
    "data": {
        "session_id": "uuid",
        "mode": "public_room",
        "status": "active",
        "topic": "Travel experiences",
        "speakers": [
            { "user_id": "uuid", "display_name": "Jane", "is_speaking": false },
            { "user_id": "uuid", "display_name": "Alex", "is_speaking": true }
        ],
        "speaker_count": 2,
        "listener_count": 15,
        "max_speakers": 5,
        "started_at": "2026-03-06T10:00:00Z"
    }
}
```

#### `session.started` (Server → All)
Session transitions to active.
```json
{
    "event": "session.started",
    "data": {
        "session_id": "uuid",
        "started_at": "2026-03-06T10:00:00Z"
    }
}
```

#### `session.ended` (Server → All)
Session has ended.
```json
{
    "event": "session.ended",
    "data": {
        "session_id": "uuid",
        "ended_at": "2026-03-06T10:30:00Z",
        "duration_sec": 1800,
        "reason": "host_ended"
    }
}
```

---

### 3. Participant Events

#### `participant.joined` (Server → All)
A new speaker joins (NOT emitted for listeners).
```json
{
    "event": "participant.joined",
    "data": {
        "user_id": "uuid",
        "display_name": "Jane",
        "role": "speaker",
        "speaker_count": 3,
        "listener_count": 16
    }
}
```

#### `participant.left` (Server → All)
A speaker leaves.
```json
{
    "event": "participant.left",
    "data": {
        "user_id": "uuid",
        "display_name": "Jane",
        "speaker_count": 2,
        "listener_count": 16
    }
}
```

#### `listener.count` (Server → All)
Periodic listener count update (debounced, every 5s max).
```json
{
    "event": "listener.count",
    "data": {
        "count": 23
    }
}
```

---

### 4. Message Events

#### `message.send` (Client → Server)
User sends a text message.
```json
{
    "event": "message.send",
    "data": {
        "content": "I think traveling solo is a great way to grow.",
        "message_type": "text"
    }
}
```

#### `message.received` (Server → All)
New message broadcast to all participants.
```json
{
    "event": "message.received",
    "data": {
        "id": "msg-uuid",
        "sender_id": "user-uuid",
        "sender_name": "Jane",
        "sender_type": "user",
        "content": "I think traveling solo is a great way to grow.",
        "message_type": "text",
        "created_at": "2026-03-06T10:05:23Z"
    }
}
```

#### `message.ai` (Server → All or Server → Sender)
AI message. In Mode 1 (ai_1on1): sent to the user. In Mode 3 (public_room): broadcast to all.
In Mode 2 (peer_1on1): AI does NOT send messages during session.
```json
{
    "event": "message.ai",
    "data": {
        "id": "msg-uuid",
        "sender_type": "ai",
        "content": "That's a great point! Solo travel can build independence. What was your most challenging solo trip?",
        "message_type": "text",
        "created_at": "2026-03-06T10:05:25Z"
    }
}
```

#### `message.ai.stream` (Server → Client)
Streaming AI response token-by-token (for ai_1on1 mode).
```json
{
    "event": "message.ai.stream",
    "data": {
        "id": "msg-uuid",
        "token": "That's",
        "is_final": false
    }
}
```
```json
{
    "event": "message.ai.stream",
    "data": {
        "id": "msg-uuid",
        "token": "",
        "is_final": true,
        "full_content": "That's a great point! Solo travel can build independence."
    }
}
```

---

### 5. Audio Events

#### `audio.chunk` (Client → Server)
Raw audio data for STT processing. Sent as **binary WebSocket frames**.

Binary frame format:
```
[1 byte: frame_type=0x01] [4 bytes: sequence_number] [rest: opus/pcm audio data]
```

#### `audio.transcription.interim` (Server → Sender)
Real-time interim STT result (for live captioning).
```json
{
    "event": "audio.transcription.interim",
    "data": {
        "text": "I think traveling solo",
        "is_final": false,
        "confidence": 0.87
    }
}
```

#### `audio.transcription.final` (Server → All)
Final transcription committed as a message.
```json
{
    "event": "audio.transcription.final",
    "data": {
        "message_id": "msg-uuid",
        "sender_id": "user-uuid",
        "sender_name": "Jane",
        "text": "I think traveling solo is a great way to grow as a person.",
        "confidence": 0.95,
        "duration_ms": 3200
    }
}
```

#### `audio.tts` (Server → Client)
TTS audio for AI responses. Sent as **binary WebSocket frames**.

Binary frame format:
```
[1 byte: frame_type=0x02] [16 bytes: message_uuid] [4 bytes: chunk_seq] [rest: audio data]
```

#### `audio.speaking.start` (Client → Server)
User starts speaking (voice activity detection).
```json
{
    "event": "audio.speaking.start",
    "data": {}
}
```

#### `audio.speaking.stop` (Client → Server)
User stops speaking.
```json
{
    "event": "audio.speaking.stop",
    "data": {}
}
```

#### `audio.speaker.active` (Server → All)
Broadcast who is currently speaking (for UI indicators).
```json
{
    "event": "audio.speaker.active",
    "data": {
        "user_id": "uuid",
        "display_name": "Jane",
        "is_speaking": true
    }
}
```

---

### 6. Moderation Events (Mode 3: Public Room only)

#### `moderation.topic.suggestion` (Server → All)
AI suggests a new topic or redirects discussion.
```json
{
    "event": "moderation.topic.suggestion",
    "data": {
        "message": "Great discussion! Let's shift to: What cultural differences surprised you most while traveling?",
        "reason": "topic_exhausted"
    }
}
```

#### `moderation.turn.prompt` (Server → Specific User)
AI prompts a quiet speaker to participate.
```json
{
    "event": "moderation.turn.prompt",
    "data": {
        "message": "Alex, we haven't heard from you in a while. Do you have any thoughts on this?",
        "target_user_id": "uuid"
    }
}
```

#### `moderation.warning` (Server → Specific User or All)
Content moderation warning.
```json
{
    "event": "moderation.warning",
    "data": {
        "message": "Let's keep the conversation respectful and on-topic.",
        "severity": "mild",
        "target_user_id": "uuid"
    }
}
```

---

### 7. Evaluation Events

#### `eval.session.ready` (Server → Speaker)
Post-session evaluation is ready to view.
```json
{
    "event": "eval.session.ready",
    "data": {
        "session_id": "uuid",
        "overall_score": 76.5,
        "url": "/eval/sessions/uuid"
    }
}
```

#### `eval.realtime.hint` (Server → Sender, Mode 1 only)
Real-time micro-feedback during AI conversation (subtle, non-intrusive).
```json
{
    "event": "eval.realtime.hint",
    "data": {
        "hint_type": "vocabulary",
        "message": "Try using 'fascinating' instead of 'interesting' for more variety.",
        "severity": "suggestion"
    }
}
```

---

### 8. System Events

#### `system.ping` / `system.pong`
Keepalive heartbeat (every 30 seconds).
```json
{ "event": "system.ping", "data": {} }
{ "event": "system.pong", "data": {} }
```

#### `system.reconnect` (Server → Client)
Server requests client reconnect (e.g., during rolling deployment).
```json
{
    "event": "system.reconnect",
    "data": {
        "reason": "server_maintenance",
        "delay_ms": 3000
    }
}
```

---

## Event Flow by Mode

### Mode 1: AI 1-on-1
```
Client                          Server                         AI Service
  │                                │                               │
  │── message.send ───────────────►│                               │
  │                                │── publish to Redis ──────────►│
  │                                │                               │── LLM call
  │◄── message.ai.stream ────────│◄── stream tokens ─────────────│
  │◄── message.ai.stream (final) ─│                               │
  │                                │── persist messages            │
  │                                │── async eval ────────────────►│ (Eval Service)
  │                                │                               │
  │── audio.chunk (binary) ───────►│── STT ───────────────────────►│ (Media Service)
  │◄── audio.transcription.interim │◄── interim ──────────────────│
  │◄── audio.transcription.final ──│◄── final ───────────────────│
  │                                │── persist + forward to AI ──►│
  │◄── audio.tts (binary) ────────│◄── TTS audio ────────────────│
```

### Mode 2: Peer 1-on-1 (AI Silent)
```
User A                         Server                         User B
  │                                │                               │
  │── message.send ───────────────►│── message.received ──────────►│
  │                                │                               │
  │                                │── publish to Redis ──────────►│ AI Service
  │                                │   (AI receives but NEVER      │ (silent)
  │                                │    sends messages back)        │
  │                                │                               │
  │◄── session.ended ────────────│── session.ended ───────────────►│
  │                                │── trigger evaluation ────────►│ Eval Service
  │◄── eval.session.ready ────────│                               │
  │                                │── eval.session.ready ────────►│
```

### Mode 3: Public Room
```
Speaker 1 ─┐                                           Listener 1 ─┐
Speaker 2 ─┼── message.send ──►┐                                    │
Speaker 3 ─┘                    │                                    │
                                ▼                                    │
                            Server                                   │
                              │                                      │
                              ├── message.received ─────────────────►┤ (broadcast)
                              │                                      │
                              ├── publish to Redis ──► AI Moderator  │
                              │                          │           │
                              │◄── moderation.* ─────────┘           │
                              │                                      │
                              ├── moderation.topic.suggestion ──────►┤ (broadcast)
                              │                                      │
                              ├── audio.speaker.active ─────────────►┤ (broadcast)
                              │                                      │
                        Listener N ─┘
```

---

## Client Reconnection Strategy

```
1. WebSocket disconnects unexpectedly
2. Client waits: min(1000 * 2^attempt, 30000) ms  (exponential backoff, max 30s)
3. Client reconnects with same JWT + session_id
4. Server sends session.state with full current state
5. Client reconciles local state with server state
6. Resume normal operation
```

Max reconnection attempts: 10. After that, show user an error and manual reconnect button.

---

## Bandwidth Considerations

| Data Type | Direction | Est. Rate |
|-----------|-----------|-----------|
| Text messages | Both | ~1 KB/msg |
| Audio chunks (Opus) | Client → Server | ~32 kbps |
| TTS audio | Server → Client | ~48 kbps |
| State events | Server → Client | ~0.5 KB/event |
| Listener broadcast (text only) | Server → Listeners | ~1 KB/msg |

Listeners receive **text only** by default. Audio streaming to listeners is opt-in (costs bandwidth).

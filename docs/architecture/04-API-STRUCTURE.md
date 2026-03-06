# API Structure

## Base URL & Versioning

```
Base: https://api.speakingapp.com/api/v1
WebSocket: wss://api.speakingapp.com/ws
```

All endpoints return JSON. All timestamps are ISO 8601 UTC.

---

## Authentication Headers

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

---

## Standard Response Envelope

```json
// Success
{
    "status": "ok",
    "data": { ... },
    "meta": { "page": 1, "per_page": 20, "total": 142 }
}

// Error
{
    "status": "error",
    "error": {
        "code": "SESSION_FULL",
        "message": "This room has reached the maximum number of speakers.",
        "details": {}
    }
}
```

---

## 1. Auth Endpoints

### `POST /api/v1/auth/register`
Create a new user account.

**Request:**
```json
{
    "email": "user@example.com",
    "display_name": "Jane Doe",
    "password": "securePassword123!"
}
```

**Response (201):**
```json
{
    "status": "ok",
    "data": {
        "user": {
            "id": "uuid",
            "email": "user@example.com",
            "display_name": "Jane Doe",
            "role": "user",
            "level": "beginner"
        },
        "tokens": {
            "access_token": "eyJ...",
            "refresh_token": "eyJ...",
            "expires_in": 900
        }
    }
}
```

### `POST /api/v1/auth/login`
Authenticate and receive tokens.

**Request:**
```json
{
    "email": "user@example.com",
    "password": "securePassword123!"
}
```

**Response (200):** Same token structure as register.

### `POST /api/v1/auth/refresh`
Refresh an expired access token.

**Request:**
```json
{
    "refresh_token": "eyJ..."
}
```

### `POST /api/v1/auth/logout`
Revoke refresh token.

### `GET /api/v1/auth/me`
Get current user profile.

### `PATCH /api/v1/auth/me`
Update current user profile (display_name, avatar_url).

---

## 2. Session Endpoints

### `POST /api/v1/sessions`
Create a new session.

**Request:**
```json
{
    "mode": "ai_1on1",
    "config": {
        "language": "en",
        "topic": "Travel experiences",
        "difficulty": "intermediate"
    }
}
```

**Response (201):**
```json
{
    "status": "ok",
    "data": {
        "session": {
            "id": "uuid",
            "mode": "ai_1on1",
            "status": "waiting",
            "config": { ... },
            "created_by": "user-uuid",
            "websocket_url": "/ws/session/uuid",
            "created_at": "2026-03-06T10:00:00Z"
        }
    }
}
```

### `GET /api/v1/sessions`
List user's sessions (paginated).

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `mode` | string | Filter by mode |
| `status` | string | Filter by status |
| `page` | int | Page number (default 1) |
| `per_page` | int | Items per page (default 20, max 50) |

### `GET /api/v1/sessions/{session_id}`
Get session details including participants and message count.

### `POST /api/v1/sessions/{session_id}/join`
Join an existing session as a speaker.

**Request:**
```json
{
    "role": "speaker"
}
```

**Response (200):**
```json
{
    "status": "ok",
    "data": {
        "participant": {
            "id": "uuid",
            "session_id": "uuid",
            "user_id": "uuid",
            "role": "speaker",
            "joined_at": "2026-03-06T10:05:00Z"
        },
        "websocket_url": "/ws/session/uuid"
    }
}
```

**Error (409):** If room is full (5 speakers).

### `POST /api/v1/sessions/{session_id}/leave`
Leave a session.

### `POST /api/v1/sessions/{session_id}/end`
End a session (creator only). Triggers evaluation pipeline.

---

## 3. Room Endpoints

### `POST /api/v1/rooms`
Create a public room.

**Request:**
```json
{
    "name": "English Practice - Travel",
    "topic": "Share your best travel stories and tips",
    "description": "Casual conversation about travel experiences",
    "max_speakers": 5,
    "config": {
        "language": "en",
        "difficulty": "intermediate",
        "ai_moderation_level": "standard"
    }
}
```

### `GET /api/v1/rooms`
List active public rooms.

**Response (200):**
```json
{
    "status": "ok",
    "data": {
        "rooms": [
            {
                "id": "uuid",
                "name": "English Practice - Travel",
                "topic": "Share your best travel stories",
                "speaker_count": 3,
                "listener_count": 12,
                "max_speakers": 5,
                "is_active": true,
                "created_at": "2026-03-06T09:00:00Z"
            }
        ]
    },
    "meta": { "page": 1, "per_page": 20, "total": 8 }
}
```

### `GET /api/v1/rooms/{room_id}`
Get room details with current session info.

### `PATCH /api/v1/rooms/{room_id}`
Update room settings (owner only).

### `DELETE /api/v1/rooms/{room_id}`
Deactivate a room (owner only).

---

## 4. Evaluation Endpoints

### `GET /api/v1/eval/sessions/{session_id}`
Get evaluation results for a specific session.

**Response (200):**
```json
{
    "status": "ok",
    "data": {
        "evaluation": {
            "id": "uuid",
            "session_id": "uuid",
            "overall_score": 76.5,
            "feedback": "Great conversation! Your fluency has improved...",
            "skills": [
                {
                    "skill_type": "speaking",
                    "score": 78.0,
                    "sub_scores": {
                        "fluency": 82,
                        "pronunciation": 75,
                        "vocabulary": 88,
                        "coherence": 79,
                        "filler_words": 66
                    },
                    "feedback": "Good fluency overall. Watch out for filler words like 'um' and 'uh'."
                },
                {
                    "skill_type": "listening",
                    "score": 80.0,
                    "sub_scores": {
                        "comprehension": 85,
                        "response_relevance": 78,
                        "follow_up_quality": 77
                    },
                    "feedback": "Strong comprehension. Try to build more on previous points."
                },
                {
                    "skill_type": "writing",
                    "score": 71.5,
                    "sub_scores": {
                        "grammar": 80,
                        "spelling": 90,
                        "vocabulary_range": 65,
                        "coherence": 60,
                        "structure": 62
                    },
                    "feedback": "Solid grammar. Try using more varied vocabulary."
                }
            ],
            "evaluated_at": "2026-03-06T10:35:00Z"
        }
    }
}
```

### `GET /api/v1/eval/history`
Get user's evaluation history (paginated).

**Query params:** `page`, `per_page`, `skill_type`, `date_from`, `date_to`

### `GET /api/v1/eval/scores/latest`
Get user's latest scores per skill.

---

## 5. Progress / Dashboard Endpoints

### `GET /api/v1/progress/dashboard`
Get aggregated dashboard data for current user.

**Response (200):**
```json
{
    "status": "ok",
    "data": {
        "current_level": "intermediate",
        "overall_score": 72.3,
        "skills": {
            "speaking": { "current": 78.0, "trend": "+3.2", "level": "intermediate" },
            "listening": { "current": 80.0, "trend": "+1.5", "level": "advanced" },
            "writing": { "current": 59.0, "trend": "+5.0", "level": "intermediate" }
        },
        "streaks": {
            "current": 5,
            "longest": 12
        },
        "recent_sessions": 3,
        "total_sessions": 47,
        "total_practice_minutes": 1420,
        "snapshots": {
            "7d": { "speaking": 76.5, "listening": 79.0, "writing": 57.0, "overall": 70.8 },
            "30d": { "speaking": 74.0, "listening": 77.5, "writing": 54.0, "overall": 68.5 },
            "all": { "speaking": 68.0, "listening": 72.0, "writing": 48.0, "overall": 62.7 }
        }
    }
}
```

### `GET /api/v1/progress/history`
Get score history over time for chart rendering.

**Query params:** `skill_type`, `period` (7d, 30d, 90d, all), `granularity` (daily, weekly)

**Response (200):**
```json
{
    "status": "ok",
    "data": {
        "skill_type": "speaking",
        "period": "30d",
        "data_points": [
            { "date": "2026-02-05", "score": 65.0, "sessions": 2 },
            { "date": "2026-02-06", "score": 68.0, "sessions": 1 },
            ...
        ]
    }
}
```

---

## 6. Transcript Endpoints

### `GET /api/v1/sessions/{session_id}/transcript`
Get full session transcript.

**Response (200):**
```json
{
    "status": "ok",
    "data": {
        "session_id": "uuid",
        "mode": "ai_1on1",
        "duration_sec": 1800,
        "messages": [
            {
                "id": "uuid",
                "sender_type": "user",
                "sender_name": "Jane Doe",
                "content": "I'd like to talk about my recent trip to Japan.",
                "message_type": "audio",
                "stt_confidence": 0.95,
                "created_at": "2026-03-06T10:00:05Z"
            },
            {
                "id": "uuid",
                "sender_type": "ai",
                "sender_name": "AI Assistant",
                "content": "That sounds wonderful! What was the highlight of your trip?",
                "message_type": "text",
                "created_at": "2026-03-06T10:00:08Z"
            }
        ]
    }
}
```

### `POST /api/v1/sessions/{session_id}/transcript/export`
Request transcript export (PDF/JSON). Returns a task ID; download URL delivered via WebSocket or polling.

---

## 7. Media Endpoints

### `POST /api/v1/media/tts`
Convert text to speech (used for AI responses in non-streaming mode).

**Request:**
```json
{
    "text": "Hello, how are you today?",
    "voice": "alloy",
    "speed": 1.0
}
```

**Response:** Audio binary stream (`audio/mpeg`).

---

## Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `VALIDATION_ERROR` | Request body validation failed |
| 401 | `UNAUTHORIZED` | Missing or invalid token |
| 403 | `FORBIDDEN` | Insufficient permissions |
| 404 | `NOT_FOUND` | Resource not found |
| 409 | `SESSION_FULL` | Room speaker slots full |
| 409 | `ALREADY_IN_SESSION` | User already in another active session |
| 422 | `SESSION_NOT_ACTIVE` | Cannot join a completed session |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |
| 503 | `AI_UNAVAILABLE` | LLM provider unavailable |

---

## Rate Limits

| Endpoint Group | Limit |
|---------------|-------|
| Auth | 10 req/min |
| Sessions | 30 req/min |
| Evaluation | 20 req/min |
| Progress | 60 req/min |
| Media (TTS) | 10 req/min |
| WebSocket messages | 60 msg/min per connection |

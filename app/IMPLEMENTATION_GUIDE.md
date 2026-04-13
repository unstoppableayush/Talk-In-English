# Flutter App Implementation Summary

## Changes Made to Sync with React Frontend

### 1. **Service Layer** (NEW)

#### `lib/core/services/room_service.dart`
- **Purpose**: Handles AI Chat room and session creation/management
- **Key Methods**:
  - `createAndJoinAiRoom()`: Creates a room and joins to get `session_id`
  - `endSession()`: Ends a chat session
  - `getSession()`: Fetches session details
  - `sendSessionMessage()`: Sends messages via session WebSocket

  **Backend Integration**:
  - REST: `POST /rooms` → Create room
  - REST: `POST /rooms/{roomId}/join` → Join room and get session_id
  - REST: `POST /sessions/{sessionId}/end` → End session

#### `lib/core/services/roleplay_service.dart`
- **Purpose**: Handles roleplay scenarios and sessions
- **Key Methods**:
  - `fetchScenarios()`: Fetches available roleplay scenarios (supports filtering)
  - `startSession()`: Starts a new roleplay session with scenario or custom topic
  - `endSession()`: Ends roleplay session
  - `sendMessage()`: Sends messages to roleplay session
  - `getReport()`: Fetches evaluation report

  **Backend Integration**:
  - REST: `GET /roleplay/scenarios` → Fetch scenarios
  - REST: `POST /roleplay/start-session` → Create roleplay session
  - REST: `POST /roleplay/sessions/{id}/end` → End session
  - REST: `GET /roleplay/report/{id}` → Get evaluation

### 2. **WebSocket Management** (NEW)

#### `lib/core/networking/websocket_manager.dart`
- **Purpose**: Unified WebSocket connection management for different protocols
- **Key Methods**:
  - `connectToAudio()`: Connect to `/ws/audio/{sessionId}` for binary audio streaming
  - `connectToRoleplay()`: Connect to `/ws/roleplay/{sessionId}` for JSON-based chat
  - `sendAudio()`: Send binary audio frames
  - `sendMessage()`: Send JSON messages
  - `sendText()`: Send plain text messages

  **Protocol Support**:
  - **Audio Protocol**: Binary PCM 16kHz audio + JSON transcription responses
  - **Roleplay Protocol**: JSON messages with events (`roleplay.message`, `roleplay.ai_reply`, etc.)

### 3. **Updated Providers**

#### `lib/features/chat/providers/ai_chat_provider.dart` (REWRITTEN)
- **Previous**: Connected to non-existent `/ai-chat` endpoint
- **Now**: 
  - Calls `RoomService.createAndJoinAiRoom()` first
  - Connects to `/ws/audio/{sessionId}` with correct token query parameter
  - Handles JSON transcription events (`transcription.result`, `ai.response`)
  - Supports binary audio transmission via `sendAudio()`
  - Methods: `startSession()`, `endSession()`, `sendMessage()`, `sendAudio()`

#### `lib/features/roleplay/providers/roleplay_provider.dart` (REWRITTEN)
- **Previous**: Connected to echo.websocket.events with hardcoded scenarios
- **Now**:
  - `loadScenarios()`: Fetches from backend
  - `selectScenario()`: Allows scenario selection with difficulty
  - `startRoleplay()`: Creates session via REST, then connects WebSocket
  - `sendMessage()`: Sends JSON messages with proper protocol
  - `endRoleplay()`: Properly ends session
  - Handles JSON roleplay events

### 4. **Updated Screens**

#### `lib/features/chat/screens/ai_chat_screen.dart` (UPDATED)
- Added session start button (only shows if no sessionId)
- Displays loading state (`isStarting`)
- Input area only visible when session is active
- Added end session button
- Proper lifecycle management

#### `lib/features/roleplay/screens/roleplay_screen.dart` (REWRITTEN)
- **Phase 1 - Scenario Selection**: Shows available scenarios from backend
- Difficulty selector (beginner/intermediate/advanced)
- **Phase 2 - Conversation**: Chat interface with message bubbles
- Start button disabled until scenario selected
- Proper loading and connection states
- End roleplay button

## Backend Endpoint Mapping

### Authentication
```
POST /auth/login           → Login with email/password
POST /auth/register        → Register with email/display_name/password
```

### Room & Session Management
```
POST /rooms                → Create room (one_on_one)
POST /rooms/{roomId}/join  → Join room → returns session_id
POST /sessions/{id}/end    → End session
GET /sessions/{id}         → Get session details
POST /sessions/{id}/messages → Send message
```

### Roleplay
```
GET /roleplay/scenarios    → List available scenarios
POST /roleplay/start-session → Create roleplay session
POST /roleplay/send-message → Send message to roleplay
POST /roleplay/sessions/{id}/end → End roleplay session
GET /roleplay/report/{id}  → Get evaluation report
```

### WebSockets
```
WS /audio/{sessionId}          → Binary audio streaming + STT/TTS
   Query params: token, language
   Sends: Binary PCM audio frames (16kHz, 16-bit)
   Receives: JSON transcription events

WS /roleplay/{sessionId}       → Roleplay conversation
   Query params: token
   Sends: JSON messages with event/data structure
   Receives: JSON roleplay events
```

## Protocol Details

### Audio Protocol (AI Chat)
- **Connection**: `ws://localhost:8000/ws/audio/{sessionId}?token=JWT&language=en`
- **Send**: Binary audio data (PCM frames)
- **Receive**: 
  ```json
  {
    "event": "transcription.result",
    "data": {
      "id": "...",
      "text": "user said this"
    }
  }
  ```
  or
  ```json
  {
    "event": "ai.response",
    "data": {
      "id": "...",
      "content": "AI reply"
    }
  }
  ```

### Roleplay Protocol
- **Connection**: `ws://localhost:8000/ws/roleplay/{sessionId}?token=JWT`
- **Send**: 
  ```json
  {
    "event": "roleplay.message",
    "data": {
      "content": "user message"
    }
  }
  ```
- **Receive**:
  ```json
  {
    "event": "roleplay.ai_reply",
    "data": {
      "id": "...",
      "content": "AI response"
    }
  }
  ```

## Key Implementation Differences from React

| Feature | React | Flutter |
|---------|-------|---------|
| State Management | Zustand | Provider |
| HTTP Client | Axios | Dio |
| WebSocket | Native WebSocket API | web_socket_channel |
| Routing | React Router | GoRouter |
| Session Creation | Implicit in hook | Explicit `startSession()` |
| Audio Recording | MediaRecorder API | (TODO: Use `record` package) |

## Architecture Overview

```
Auth Flow
├─ Login/Register via REST
├─ Token stored in ApiClient
├─ All requests auto-include Bearer token

AI Chat Flow
├─ startSession() 
│  ├─ REST: Create room
│  ├─ REST: Join room → get sessionId
│  └─ WS: Connect to /audio/{sessionId}
├─ sendMessage() or sendAudio()
├─ Listen for transcription/response events
└─ endSession() → REST: End session

Roleplay Flow
├─ loadScenarios()
│  └─ REST: GET /roleplay/scenarios
├─ selectScenario() + setDifficulty()
├─ startRoleplay()
│  ├─ REST: POST /roleplay/start-session
│  └─ WS: Connect to /roleplay/{sessionId}
├─ sendMessage()
├─ Listen for roleplay events
└─ endRoleplay() → REST: End session
```

## TODO Items

### High Priority
1. **Audio Recording Implementation**
   - Add `record` package to pubspec.yaml
   - Implement audio capture from microphone
   - Convert to PCM 16kHz, 16-bit format
   - Stream to WebSocket in `sendAudio()`

2. **Error Handling**
   - Add proper exception handling in all services
   - User-facing error messages
   - Automatic reconnection on WebSocket disconnect

3. **Testing**
   - Compile and run on Flutter emulator
   - Test auth flow
   - Test AI Chat session creation and messaging
   - Test Roleplay scenario selection and conversation

### Medium Priority
1. **Message Models**
   - Create proper type-safe message models
   - Add serialization/deserialization

2. **Scoring & Evaluation**
   - Implement score display after session
   - Fetch and display evaluation reports

3. **Player Report Pages**
   - Implement score report display
   - Show evaluation metrics

### Lower Priority
1. **Google Auth**
   - Implement via `google_sign_in` package
   - Update backend integration

2. **Peer Chat**
   - Similar pattern to AI Chat but for multi-user
   - Session-based WebSocket

## Files Modified

- `lib/core/networking/api_client.dart` - No changes needed
- `lib/core/networking/websocket_manager.dart` - **NEW**
- `lib/core/services/room_service.dart` - **NEW**
- `lib/core/services/roleplay_service.dart` - **NEW**
- `lib/features/auth/providers/auth_provider.dart` - Already synced with backend
- `lib/features/chat/providers/ai_chat_provider.dart` - **Rewritten**
- `lib/features/chat/screens/ai_chat_screen.dart` - **Updated**
- `lib/features/roleplay/providers/roleplay_provider.dart` - **Rewritten**
- `lib/features/roleplay/screens/roleplay_screen.dart` - **Rewritten**
- `lib/features/dashboard/screens/dashboard_screen.dart` - Not changed
- `lib/features/peer_chat/` - Not changed

## Compilation Next Steps

1. Run `flutter pub get` to download dependencies
2. Run `flutter analyze` to check for errors
3. Run `flutter run` on emulator
4. Test authentication flow
5. Test AI Chat feature (create session → connect WebSocket)
6. Test Roleplay feature (load scenarios → select → start → chat)

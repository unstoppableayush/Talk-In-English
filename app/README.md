# Speaking App - Flutter Client

This is the Flutter-based frontend for the Speaking App, built with a feature-first architecture, modern Material 3 design, and highly decoupled state management.

## 🏗️ Architecture & Tech Stack

- **Framework:** Flutter (Dart)
- **State Management:** [Provider](https://pub.dev/packages/provider) for global and feature-level state.
- **Routing:** [GoRouter](https://pub.dev/packages/go_router) for deep linking and shell route-based navigation.
- **Networking:** 
  - [Dio](https://pub.dev/packages/dio) for REST API tracking and Token interceptors.
  - [web_socket_channel](https://pub.dev/packages/web_socket_channel) for real-time bidirectional communication.
- **Design System:** Material 3 with a customized Indigo & Dark theme.

## 📂 Folder Structure

```text
lib/
├── core/                   # Shared utilities, networking, and theming
│   ├── networking/         # Dio ApiClient & Interceptors
│   ├── router/             # GoRouter configuration
│   └── theme/              # AppTheme definitions
├── features/               # Feature-first domain layer
│   ├── auth/               # Login & Registration screens + AuthProvider
│   ├── dashboard/          # Dashboard screen
│   ├── chat/               # AI Chat interface & WebSocket Provider
│   ├── peer_chat/          # Peer-to-Peer messaging
│   └── roleplay/           # Interactive AI Roleplay feature
└── main.dart               # Application entry point
```

## ✨ Implemented Features

1. **Authentication (`features/auth`)**:
   - Login and Registration flows connected via Dio to `127.0.0.1:8000/api/v1`.
   - Form fields synchronized with the backend REST payloads: `email`, `display_name`, and `password`.
   - UI integrated with standard Email inputs as well as "Continue with Google" buttons.
   - Token-based auth logic that extracts JSON Web Tokens (`access_token`) and persists them in memory to be automatically attached as `Bearer` headers to subsequent requests.

2. **Navigation & Dashboard (`features/dashboard`)**:
   - Set up using `ShellRoute` in GoRouter to maintain persistent bottom navigation.
   - Grid-based landing page showcasing AI Chat, Roleplay, and Peer Chat features.

3. **AI Chat (`features/chat`)**:
   - Scaffolded message UI and provider state (`AiChatProvider`).
   - *Note: WebSocket integration in progress (Migrating from text-based echo testing to PCM 16-bit binary audio streams corresponding to backend `/ws/audio/{session_id}`).*

4. **Roleplay (`features/roleplay`)**:
   - Interactive roleplay interface scaffolding.
   - Associated `RoleplayProvider`.
   - *Note: Similar to AI Chat, backend integration for the `/ws/roleplay-audio/{session_id}` endpoint is underway.*

5. **Peer Chat (`features/peer_chat`)**:
   - Chat room scaffolding for multiple active human users.

## 🚀 Getting Started

### Prerequisites
- Flutter SDK (3.x)
- Running local Python backend on `http://127.0.0.1:8000`

### Setup

1. Fetch dependencies:
   ```bash
   flutter pub get
   ```

2. Run the application:
   ```bash
   flutter run
   ```

## 🔄 Next Steps
- Implement real-time audio chunk recording using a mic package (e.g., `record`).
- Complete the WebSocket integrations (`ai_chat_provider.dart` and `roleplay_provider.dart`) to transmit and receive PCM audio binary blobs per the React and Python architecture schemas.

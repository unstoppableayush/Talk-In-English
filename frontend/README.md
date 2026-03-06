# Speaking App — Frontend

React 18 + TypeScript + Vite frontend for the Speaking App. Provides the full user interface for AI conversations, peer chat, public rooms, roleplay, scoring, and admin management.

---

## Table of Contents

- [Folder Structure](#folder-structure)
- [Tech Stack](#tech-stack)
- [Pages — What Each Page Does](#pages)
- [Routing Map](#routing-map)
- [State Management](#state-management)
- [API Layer](#api-layer)
- [WebSocket Layer](#websocket-layer)
- [Types (TypeScript Interfaces)](#types)
- [Layouts](#layouts)
- [Styling](#styling)
- [Setup & Run](#setup--run)
- [How to Modify Common Things](#how-to-modify-common-things)

---

## Folder Structure

```
frontend/
├── src/
│   ├── main.tsx                # React entry point (StrictMode + BrowserRouter + QueryClientProvider)
│   ├── App.tsx                 # All route definitions + ProtectedRoute guard
│   ├── index.css               # Tailwind CSS base imports + custom theme
│   │
│   ├── pages/                  # One file per page/screen
│   │   ├── auth/
│   │   │   ├── LoginPage.tsx       # Email + password login form
│   │   │   └── RegisterPage.tsx    # Registration form (name, email, password, languages)
│   │   ├── DashboardPage.tsx       # XP, streak, session stats, dimension charts
│   │   ├── AIConversationPage.tsx  # 1-on-1 AI chat with message bubbles
│   │   ├── PeerChatPage.tsx        # Find/create peer rooms + join
│   │   ├── PublicRoomPage.tsx      # Multi-speaker room (5 slots, listeners, moderator)
│   │   ├── RolePlayPage.tsx        # AI roleplay — scenario select → conversation → report
│   │   ├── ScoreReportPage.tsx     # Post-session scores (radar chart, bar chart, AI feedback)
│   │   └── AdminPanelPage.tsx      # Admin dashboard — manage rooms + users
│   │
│   ├── layouts/                # Page wrapper layouts
│   │   ├── AppLayout.tsx           # Sidebar nav + main content area (for logged-in users)
│   │   └── AuthLayout.tsx          # Centered card layout (for login/register)
│   │
│   ├── hooks/                  # Custom React hooks
│   │   └── useSessionSocket.ts     # WebSocket connection hook for chat sessions
│   │
│   ├── stores/                 # Zustand state stores
│   │   ├── authStore.ts            # JWT tokens, user profile, login/logout
│   │   └── roomStore.ts            # Room state, messages, participants
│   │
│   ├── lib/                    # Utility libraries
│   │   ├── api.ts                  # Axios instance with JWT interceptors + auto-refresh
│   │   └── ws.ts                   # WebSocket URL builder with auth token
│   │
│   └── types/                  # TypeScript interfaces
│       └── index.ts                # All shared types (User, Room, Session, Score, Roleplay, etc.)
│
├── index.html                  # Vite HTML entry
├── package.json                # Dependencies + scripts
├── vite.config.ts              # Vite config with @ path alias
├── tsconfig.json               # TypeScript config
├── tailwind.config.js          # Tailwind with primary color palette
├── postcss.config.js           # PostCSS (Tailwind + Autoprefixer)
├── nginx-spa.conf              # Production nginx config for SPA routing
├── Dockerfile                  # Production build (Node 22 → nginx 1.27)
└── .dockerignore
```

---

## Tech Stack

| Library | Version | Purpose |
|---------|---------|---------|
| React | 18.3 | UI framework |
| TypeScript | 5.6 | Type safety |
| Vite | 6.x | Dev server + bundler |
| React Router | 6.28 | Client-side routing |
| TanStack Query | 5.60 | Server state / data fetching |
| Zustand | 5.0 | Client state management |
| Axios | 1.7 | HTTP client with interceptors |
| Recharts | 2.14 | Charts (radar, bar) |
| Lucide React | 0.460 | Icon library |
| Tailwind CSS | 3.4 | Utility-first styling |

---

## Pages

### LoginPage (`/auth/login`)
- Email + password form
- Calls `POST /api/v1/auth/login`
- Stores JWT tokens in Zustand (persisted to localStorage)
- Redirects to Dashboard on success

### RegisterPage (`/auth/register`)
- Display name, email, password, native language, target language
- Calls `POST /api/v1/auth/register`
- Auto-logs in after registration

### DashboardPage (`/`)
- Fetches `GET /api/v1/progress/dashboard`
- Shows: XP, streak days, total sessions, practice minutes
- Dimension averages as stat cards
- Quick-start buttons for AI Chat, Peer Chat, Role Play

### AIConversationPage (`/ai-chat`)
- Creates a 1-on-1 room via `POST /api/v1/rooms`
- Connects to `ws://.../ws/{session_id}` using `useSessionSocket` hook
- Real-time message bubbles (user = blue right, AI = gray left)
- Text input with send button

### PeerChatPage (`/peer-chat`)
- Fetches active public rooms via `GET /api/v1/rooms`
- Filter by language
- Create new room button
- Click room → navigates to `/room/{roomId}`

### PublicRoomPage (`/room/:roomId`)
- Pre-join screen (choose speaker/listener role)
- 5-slot speaker grid with speaking indicators
- Listener sidebar list with promote-to-speaker button
- AI moderator bar (shows AI intervention suggestions)
- Live transcript panel
- Mute toggle, raise hand, session timer, leave button
- Uses `useSessionSocket` for WebSocket connection

### RolePlayPage (`/roleplay`)
**3 phases in one page:**

1. **Setup Phase** — Two tabs:
   - "Predefined Scenarios" — grid of scenario cards (fetched from `GET /api/v1/roleplay/scenarios`)
   - "Custom Topic" — free-text input
   - Difficulty selector (beginner/intermediate/advanced)
   - Start button → calls `POST /api/v1/roleplay/start-session`

2. **Conversation Phase:**
   - Connects via WebSocket to `ws://.../ws/roleplay/{session_id}`
   - AI/user message bubbles
   - Session timer
   - End Session button → sends `{"event": "roleplay.end"}`

3. **Report Phase:**
   - Polls `GET /api/v1/roleplay/report/{session_id}` until evaluation ready
   - Overall score circle
   - 7 dimension score cards (Fluency, Grammar, Vocabulary, Confidence, Clarity, Relevance, Consistency)
   - Strengths (green), Weaknesses (yellow), Improvement Tips (blue)
   - Filler words detected with counts

### ScoreReportPage (`/scores/:sessionId`)
- Fetches scores + feedback from eval API
- Radar chart (8 dimensions)
- Horizontal bar chart
- Overall score circle with XP earned
- AI feedback cards: summary, strengths, improvements, suggested exercises

### AdminPanelPage (`/admin`)
- Two tabs: Rooms, Users
- Rooms table: name, type, language, speakers, status, delete button
- Users table: name, email, role badge, XP, status
- Refresh button

---

## Routing Map

Defined in `App.tsx`:

| Path | Page | Auth Required | Layout |
|------|------|---------------|--------|
| `/auth/login` | LoginPage | No | AuthLayout |
| `/auth/register` | RegisterPage | No | AuthLayout |
| `/` | DashboardPage | Yes | AppLayout |
| `/ai-chat` | AIConversationPage | Yes | AppLayout |
| `/peer-chat` | PeerChatPage | Yes | AppLayout |
| `/room/:roomId` | PublicRoomPage | Yes | AppLayout |
| `/roleplay` | RolePlayPage | Yes | AppLayout |
| `/scores/:sessionId` | ScoreReportPage | Yes | AppLayout |
| `/admin` | AdminPanelPage | Yes | AppLayout |
| `*` | Redirect → `/` | — | — |

**To add a new page:**
1. Create `src/pages/MyPage.tsx`
2. Add import + `<Route>` in `App.tsx`
3. Add nav link in `AppLayout.tsx` (import icon from lucide-react)

---

## State Management

### `authStore.ts` (Zustand + localStorage persistence)
```
State:
  accessToken: string | null
  refreshToken: string | null
  user: User | null

Actions:
  login(email, password)    → calls API, stores tokens + user
  register(data)            → calls API, stores tokens + user
  setTokens(access, refresh)
  logout()                  → clears everything
```

### `roomStore.ts` (Zustand)
```
State:
  room: Room | null
  participants: Participant[]
  messages: ChatMessage[]
  isMuted: boolean

Actions:
  setRoom(room)
  addMessage(msg)
  setParticipants(list)
  toggleMute()
  reset()
```

---

## API Layer

**File:** `src/lib/api.ts`

- Axios instance with `baseURL: '/api/v1'`
- **Request interceptor:** Attaches `Authorization: Bearer <token>` header
- **Response interceptor:** On 401, attempts token refresh via `POST /api/v1/auth/refresh`, then retries the original request. If refresh fails, logs out.

**Usage in any component:**
```tsx
import api from '@/lib/api';

// GET request
const { data } = await api.get('/rooms');

// POST request
const { data } = await api.post('/roleplay/start-session', { custom_topic: 'AI', difficulty: 'intermediate' });
```

---

## WebSocket Layer

### `src/lib/ws.ts` — URL Builder
```tsx
import { buildWSUrl } from '@/lib/ws';

const url = buildWSUrl(`/roleplay/${sessionId}`);
// → "ws://localhost:5173/ws/roleplay/abc123?token=eyJ..."
```

### `src/hooks/useSessionSocket.ts` — Chat Hook
Connects to `ws://.../ws/{session_id}`, handles events:
- `chat.message` → adds to roomStore messages
- `session.user_joined` / `session.user_left` → updates participants
- `moderation.action` → shows AI moderation alerts
- Returns `{ sendMessage }` function

### RolePlayPage — inline WebSocket
The roleplay page manages its own WebSocket directly (not via the shared hook) because it has unique events (`roleplay.message`, `roleplay.ai_reply`, `roleplay.end`).

---

## Types

**File:** `src/types/index.ts`

| Interface | Used By |
|-----------|---------|
| `User` | Auth, Dashboard, Admin |
| `Tokens` | Auth store |
| `AuthResponse` | Login/Register |
| `Room` | PeerChat, PublicRoom, Admin |
| `Participant` | PublicRoom |
| `SessionScore` | ScoreReport |
| `AIFeedback` | ScoreReport |
| `DimensionAvg` | Dashboard |
| `Dashboard` | DashboardPage |
| `ChatMessage` | AI Chat, Public Room |
| `WSEvent<T>` | WebSocket handlers |
| `RoleplayScenario` | RolePlayPage |
| `RoleplaySession` | RolePlayPage |
| `RoleplayMessage` | RolePlayPage |
| `RoleplayEvaluation` | RolePlayPage |

---

## Layouts

### AppLayout (`layouts/AppLayout.tsx`)
- Fixed left sidebar (w-64) — dark background
- Logo + app name at top
- Navigation links (each has icon + label)
- User info + sign out at bottom
- `<Outlet />` for page content on the right

**Navigation links** (modify the `links` array to add/remove):
```tsx
const links = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/ai-chat', label: 'AI Chat', icon: MessageSquare },
  { to: '/peer-chat', label: 'Peer Chat', icon: Users },
  { to: '/roleplay', label: 'Role Play', icon: Theater },
  { to: '/admin', label: 'Admin', icon: Shield },
];
```

### AuthLayout (`layouts/AuthLayout.tsx`)
- Centered card on gradient background
- `<Outlet />` for login/register form

---

## Styling

- **Tailwind CSS 3.4** with a custom primary color palette (`primary-50` through `primary-900`)
- Configured in `tailwind.config.js`
- Base styles in `src/index.css`
- No component library — all UI is hand-crafted with Tailwind utility classes
- Common patterns:
  - Cards: `rounded-xl bg-white p-5 shadow-sm`
  - Buttons: `rounded-lg bg-primary-600 px-4 py-2 text-white hover:bg-primary-700`
  - Inputs: `rounded-lg border border-gray-300 px-4 py-3 focus:border-primary-500 focus:ring-1 focus:ring-primary-500`

---

## Setup & Run

### Local Development

```bash
cd frontend
npm install
npm run dev
```

Runs at `http://localhost:5173` with Vite HMR.

The Vite config proxies `/api` and `/ws` to the backend at `localhost:8000`.

### Build for Production

```bash
npm run build
# Output in dist/
```

### With Docker

```bash
# From project root
docker-compose up frontend
# Runs at http://localhost:5173
```

### Production Docker

The `Dockerfile` creates a two-stage build:
1. **Build stage:** Node 22 → `npm run build`
2. **Runtime stage:** nginx 1.27 serving the built `dist/` with SPA fallback (`nginx-spa.conf`)

---

## How to Modify Common Things

### Add a new page
1. Create `src/pages/MyNewPage.tsx`
2. In `App.tsx`: import it, add `<Route path="/my-page" element={<MyNewPage />} />` inside the protected route block
3. In `layouts/AppLayout.tsx`: add `{ to: '/my-page', label: 'My Page', icon: SomeLucideIcon }` to the `links` array (import the icon from `lucide-react`)

### Add a new API call
```tsx
import api from '@/lib/api';

// In a component or hook:
const { data } = await api.get('/my-endpoint');
const { data } = await api.post('/my-endpoint', body);
```

Or with TanStack Query:
```tsx
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

const { data, isLoading } = useQuery({
  queryKey: ['my-data'],
  queryFn: () => api.get('/my-endpoint').then(r => r.data),
});
```

### Add a new TypeScript type
Add it to `src/types/index.ts`:
```ts
export interface MyNewType {
  id: string;
  name: string;
}
```

### Change the sidebar navigation
Edit the `links` array in `src/layouts/AppLayout.tsx`. Icons come from [lucide.dev](https://lucide.dev).

### Change Tailwind colors
Edit `tailwind.config.js` → `theme.extend.colors.primary` object.

### Add a new Zustand store
Create `src/stores/myStore.ts`:
```ts
import { create } from 'zustand';

interface MyState {
  value: string;
  setValue: (v: string) => void;
}

export const useMyStore = create<MyState>((set) => ({
  value: '',
  setValue: (v) => set({ value: v }),
}));
```

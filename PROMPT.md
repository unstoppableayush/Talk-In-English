PHASE 1 — Project Architecture Setup

✅ Prompt 1: Generate Full Architecture
Act as a senior system architect.

Help me design a scalable AI-powered communication platform with these features:

1) 1-to-1 AI conversation mode
2) 1-to-1 peer conversation with AI monitoring silently
3) Public room with max 5 speakers (AI moderates)
4) Unlimited listeners (not tracked by AI)
5) Speaking, Listening, Writing evaluation
6) AI scoring system per user
7) Session transcript storage
8) Progress dashboard

Tech stack:
- Backend: FastAPI
- Frontend: React
- Database: PostgreSQL
- Real-time: WebSockets
- AI: LLM API
- Speech-to-Text + Text-to-Speech

Give me:
- High-level architecture
- Microservices breakdown
- Database schema design
- API structure
- WebSocket event design
- Scalability strategy


🔹PHASE 2 — Database Design
✅ Prompt 2: Database Schema
Act as a database architect.

Design a normalized PostgreSQL schema for:

Users
Rooms
Room Participants (Speaker / Listener)
Messages (real-time transcripts)
AI Feedback Reports
Session Scores (fluency, clarity, grammar, leadership, etc.)
Section Tests (speaking, listening, writing)
Leaderboard (for public rooms)

Provide:
- Table structure
- Primary keys
- Foreign keys
- Indexing strategy
- ER relationship explanation

🔹 PHASE 3 — Backend (FastAPI)

✅ Prompt 3: Authentication Module
Generate production-ready FastAPI code for:

- User registration
- Login with JWT authentication
- Password hashing (bcrypt)
- Role-based access control
- Middleware protection

✅ Prompt 4: Room Management APIs
Create FastAPI endpoints for:

- Create room (public / private / 1-1)
- Join room
- Leave room
- Promote listener to speaker
- Raise hand feature
- End session

Include:
- Request/response models
- Validation
- Proper status codes

✅ Prompt 5: WebSocket Real-Time System
Generate FastAPI WebSocket implementation for:

- Real-time messaging
- Multi-user public room (max 5 speakers)
- Listener mode
- Broadcast messages to room
- Maintain connected users list
- Disconnect handling

Design it scalable.

🔹 PHASE 4 — AI Integration

✅ Prompt 6: AI Conversation Logic
Help me integrate LLM API for:

1) 1-to-1 AI conversation
2) AI moderation in group discussion
3) AI silent monitoring in peer 1-1
4) Real-time communication analysis

Design:
- Prompt templates
- Context memory storage
- Session-based conversation handling

✅ Prompt 7: Scoring Engine
Create AI evaluation prompt that scores users on:

Speaking:
- Fluency
- Grammar
- Vocabulary
- Confidence
- Filler words
- Speaking speed

Public Room:
- Participation
- Leadership
- Listening skill
- Relevance

Return structured JSON response.

🔹 PHASE 5 — Speech Processing

✅ Prompt 8: Speech-to-Text + Text-to-Speech
Design integration for:

- Real-time Speech-to-Text
- Text-to-Speech response
- Audio streaming via WebSockets
- Pronunciation analysis

Optimize for low latency.

🔹 PHASE 6 — React Frontend

✅ Prompt 9: Frontend Structure
Act as senior React architect.

Create project structure for:

- Auth pages
- Dashboard
- 1-to-1 AI Chat page
- Peer Chat page
- Public Room page
- Listener Mode UI
- Score Report page
- Admin panel

Include:
- Folder structure
- State management
- WebSocket integration
- Protected routes

✅ Prompt 10: Public Room UI

Build a modern UI design for:

- 5 speaker video/audio slots
- Listener panel
- Raise hand button
- AI moderator messages
- Live transcript panel
- Timer
- End session button

Use React + Tailwind.

🔹 PHASE 7 — AI Monitoring Logic

✅ Prompt 11: Silent AI Monitoring
Design backend logic where:

Two users talk 1-to-1.
AI does NOT interrupt.
AI stores transcript.
At session end:
- Analyze full conversation
- Give individual scores
- Provide strengths/weaknesses
- Provide improvement roadmap
🔹 PHASE 8 — Section-Based Testing System

✅ Prompt 12: Section Mode Design
Design 3 independent modules:

1) Speaking test (AI asks question, user responds)
2) Listening test (AI plays audio, user answers)
3) Writing test (User writes essay, AI scores)

Allow:
- Full test mode
- Single section mode
- Timed mode
- Instant scoring
🔹 PHASE 9 — Analytics & Dashboard

✅ Prompt 13: Progress Analytics
Design user dashboard showing:

- Overall communication score
- Section-wise breakdown
- Historical performance chart
- Public room ranking
- Weakness analysis
- AI improvement suggestions

🔹 PHASE 10 — Production & Scaling
✅ Prompt 14: Deployment Strategy
Design production-ready deployment architecture:

- Docker containers
- Nginx reverse proxy
- PostgreSQL cloud hosting
- Redis for WebSocket scaling
- Horizontal scaling strategy
- Rate limiting
- Logging & monitoring
- Security best practices

Phase 11 — AI Role-Play Speaking Module (Prompt)

Use this prompt when building the next feature of your platform.

Act as a senior AI system architect and full-stack developer.

I am building an AI-powered communication practice platform.

Current stack:
Backend: FastAPI
Frontend: React
Database: PostgreSQL
Real-time communication: WebSockets
AI: LLM API
Speech processing: Speech-to-Text and Text-to-Speech

The platform already has:
1. Authentication
2. User dashboard
3. 1-to-1 AI conversation
4. Peer 1-to-1 communication
5. Public discussion rooms
6. AI monitoring and scoring
7. Speaking/Listening/Writing test sections
8. Session transcript storage
9. User performance analytics
10. Deployment architecture

Now design and implement:

PHASE 11: AI ROLE-PLAY SPEAKING MODULE

------------------------------------------------

FEATURE GOAL

Create a Role-Play conversation system where users can speak with AI on any topic and AI behaves like a human conversational partner.

The AI should:
- talk naturally
- ask follow-up questions
- continue the conversation
- encourage the user to speak more
- simulate real-life situations
- evaluate speaking performance

------------------------------------------------

USER FLOW

1. User opens "AI Role Play" section.

2. User can choose:

A) Predefined scenario
Examples:
- Job Interview
- Customer Support Call
- Ordering Food
- Business Meeting
- College Presentation
- Friendly Conversation

OR

B) Custom Topic

User can type any topic like:
- "Talk about technology"
- "Discuss climate change"
- "Practice English conversation"
- "Debate about AI"

3. User selects difficulty level:
- Beginner
- Intermediate
- Advanced

4. User clicks "Start Role Play".

5. AI introduces the conversation.

Example:

"Hello! Let's start our conversation. Tell me what you think about this topic."

6. User speaks using microphone.

7. Speech is converted to text using Speech-to-Text.

8. AI processes the message and replies using the LLM.

9. AI reply is optionally converted to voice using Text-to-Speech.

10. Conversation continues for a defined session length (5–10 minutes).

11. All conversation messages are stored in the database.

12. When the session ends, AI analyzes the full conversation.

------------------------------------------------

AI BEHAVIOR RULES

The AI should:

- respond like a real human
- keep responses short and conversational
- ask open-ended questions
- encourage the user to explain ideas
- challenge the user with follow-up questions
- maintain topic context

Example behavior:

User: I think technology is changing education.

AI: Interesting point. Can you explain how technology is improving education?

------------------------------------------------

SPEAKING SKILL EVALUATION

After the session ends, AI should analyze the full transcript.

Evaluation categories:

1. Fluency
2. Grammar Accuracy
3. Vocabulary Usage
4. Communication Clarity
5. Confidence
6. Response Relevance
7. Speaking Consistency

The AI should return a structured JSON report.

Example output:

{
  "fluency_score": 8,
  "grammar_score": 7,
  "vocabulary_score": 6,
  "confidence_score": 8,
  "clarity_score": 7,
  "relevance_score": 8,
  "overall_score": 7.4,

  "strengths": [
    "Good fluency while explaining ideas",
    "Clear communication style"
  ],

  "weaknesses": [
    "Minor grammar mistakes",
    "Limited vocabulary usage"
  ],

  "improvement_suggestions": [
    "Practice using more advanced vocabulary",
    "Avoid repeating simple sentence structures"
  ]
}

------------------------------------------------

ROLE PLAY SCENARIO ENGINE

Create a scenario system.

Each scenario should contain:

scenario_id
scenario_title
scenario_description
ai_role
user_role
difficulty
starting_prompt
expected_topics

Example:

scenario_title: Job Interview
ai_role: Hiring Manager
user_role: Candidate
starting_prompt: "Welcome to the interview. Please introduce yourself."

------------------------------------------------

DATABASE DESIGN

Create PostgreSQL tables for:

RoleplayScenarios
RoleplaySessions
RoleplayMessages
RoleplayEvaluationReports

RoleplaySessions table should include:

session_id
user_id
scenario_id
custom_topic
start_time
end_time
session_duration
transcript
evaluation_report

------------------------------------------------

BACKEND IMPLEMENTATION (FASTAPI)

Create APIs:

GET /roleplay/scenarios
POST /roleplay/start-session
POST /roleplay/send-message
POST /roleplay/end-session
GET /roleplay/report/{session_id}

Use WebSockets for real-time conversation streaming.

------------------------------------------------

FRONTEND IMPLEMENTATION (REACT)

Create components:

RolePlayDashboard
ScenarioSelector
CustomTopicInput
ConversationInterface
MicrophoneRecorder
LiveTranscriptViewer
SessionTimer
EndSessionButton
EvaluationReportPage

Conversation interface should show:

AI messages
User messages
Microphone button
Live transcript
Session timer

------------------------------------------------

AI PROMPT TEMPLATE

Create a prompt template:

"You are a human conversational partner in a role-play session.

Topic: [TOPIC]

Scenario: [SCENARIO_DESCRIPTION]

Rules:
- respond naturally
- keep responses conversational
- ask follow-up questions
- encourage the user to speak more
- stay on the topic

Conversation history:
[CHAT_HISTORY]

Respond as a human conversational partner."

------------------------------------------------

END SESSION ANALYSIS PROMPT

Create an AI prompt that analyzes the entire transcript and generates the structured evaluation report.

------------------------------------------------

BONUS FEATURES

Optional advanced features:

1. Filler word detection (um, uh, like)
2. Speaking speed analysis
3. Vocabulary diversity scoring
4. Keyword coverage scoring
5. AI improvement tips
6. Replay conversation
7. Download evaluation report
8. Progress comparison with previous sessions

------------------------------------------------

DELIVERABLES

Provide:

- FastAPI backend structure
- PostgreSQL schema
- React frontend architecture
- WebSocket conversation system
- AI prompt templates
- Sample role-play scenarios
- Example evaluation reports

Ensure the system is modular and scalable.
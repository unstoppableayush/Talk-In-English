// Common types matching backend Pydantic schemas

export interface User {
  id: string;
  email: string;
  display_name: string;
  native_language: string | null;
  target_language: string | null;
  xp: number;
  streak_days: number;
  avatar_url: string | null;
  created_at: string;
}

export interface Tokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

export interface AuthResponse {
  user: User;
  tokens: Tokens;
}

export interface Room {
  id: string;
  name: string;
  room_type: 'public' | 'private' | 'one_on_one';
  topic: string | null;
  description: string | null;
  language: string;
  max_speakers: number;
  is_active: boolean;
  speaker_count: number;
  listener_count: number;
  created_at: string;
}

export interface Participant {
  id: string;
  session_id: string;
  user_id: string;
  role: 'speaker' | 'listener';
  hand_raised: boolean;
  speaking_duration_sec: number;
  joined_at: string;
}

export interface SessionScore {
  id: string;
  session_id: string;
  user_id: string;
  fluency: number;
  clarity: number;
  grammar: number;
  vocabulary: number;
  coherence: number;
  leadership: number;
  engagement: number;
  turn_taking: number;
  overall: number;
  xp_earned: number;
  scored_at: string;
}

export interface AIFeedback {
  id: string;
  session_id: string;
  user_id: string;
  dimension_feedback: Record<string, string>;
  strengths: string[];
  improvement_areas: string[];
  suggested_exercises: string[];
  summary: string | null;
  model_used: string;
  created_at: string;
}

export interface DimensionAvg {
  fluency: number | null;
  clarity: number | null;
  grammar: number | null;
  vocabulary: number | null;
  coherence: number | null;
  leadership: number | null;
  engagement: number | null;
  turn_taking: number | null;
  overall: number | null;
}

export interface Dashboard {
  xp: number;
  streak_days: number;
  recent_sessions: number;
  total_sessions: number;
  total_practice_minutes: number;
  snapshots: Record<string, DimensionAvg>;
}

export interface ChatMessage {
  id: string;
  sender_id: string;
  sender_name: string;
  sender_type: 'user' | 'ai';
  content: string;
  message_type: string;
  created_at: string;
}

export interface WSEvent<T = unknown> {
  event: string;
  data: T;
}

// ── Roleplay types ──────────────────────────────────────────

export interface RoleplayScenario {
  id: string;
  title: string;
  description: string | null;
  category: string;
  ai_role: string;
  user_role: string;
  difficulty: string;
  language: string;
  starting_prompt: string | null;
  expected_topics: string[] | null;
}

export interface RoleplaySession {
  id: string;
  user_id: string;
  scenario_id: string | null;
  custom_topic: string | null;
  difficulty: string;
  language: string;
  status: 'active' | 'completed' | 'cancelled';
  started_at: string;
  ended_at: string | null;
  duration_sec: number | null;
}

export interface RoleplayMessage {
  id: string;
  session_id: string;
  sender: 'user' | 'ai';
  content: string;
  created_at: string;
}

export interface RoleplayEvaluation {
  id: string;
  session_id: string;
  user_id: string;
  fluency: number;
  grammar: number;
  vocabulary: number;
  confidence: number;
  clarity: number;
  relevance: number;
  consistency: number;
  overall_score: number;
  xp_earned: number;
  strengths: string[];
  weaknesses: string[];
  improvement_suggestions: string[];
  filler_words: Record<string, number>;
}

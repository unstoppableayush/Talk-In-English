import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { buildWSUrl } from '@/lib/ws';
import type {
  RoleplayScenario,
  RoleplaySession,
  RoleplayMessage,
  RoleplayEvaluation,
} from '@/types';
import {
  Theater,
  Pen,
  Play,
  Send,
  Square,
  Clock,
  ChevronLeft,
  Star,
  TrendingUp,
  TrendingDown,
  Lightbulb,
  ArrowRight,
} from 'lucide-react';

type Phase = 'setup' | 'conversation' | 'report';
type Difficulty = 'beginner' | 'intermediate' | 'advanced';

export default function RolePlayPage() {
  const [phase, setPhase] = useState<Phase>('setup');

  // ── Setup state ──
  const [tab, setTab] = useState<'scenarios' | 'custom'>('scenarios');
  const [selectedScenario, setSelectedScenario] = useState<RoleplayScenario | null>(null);
  const [customTopic, setCustomTopic] = useState('');
  const [difficulty, setDifficulty] = useState<Difficulty>('intermediate');
  const [starting, setStarting] = useState(false);

  // ── Conversation state ──
  const [session, setSession] = useState<RoleplaySession | null>(null);
  const [messages, setMessages] = useState<RoleplayMessage[]>([]);
  const [input, setInput] = useState('');
  const [aiTyping, setAiTyping] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Report state ──
  const [evaluation, setEvaluation] = useState<RoleplayEvaluation | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  // ── Fetch scenarios ──
  const { data: scenarios = [] } = useQuery<RoleplayScenario[]>({
    queryKey: ['roleplay-scenarios'],
    queryFn: () => api.get('/roleplay/scenarios').then((r) => r.data),
  });

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, aiTyping]);

  // Timer
  useEffect(() => {
    if (phase === 'conversation') {
      timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [phase]);

  // Cleanup WS on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // ── Start session ──
  const startSession = async () => {
    if (!selectedScenario && !customTopic.trim()) return;
    setStarting(true);
    try {
      const body: Record<string, unknown> = { difficulty, language: 'en' };
      if (selectedScenario) body.scenario_id = selectedScenario.id;
      else body.custom_topic = customTopic.trim();

      const { data } = await api.post<{
        session: RoleplaySession;
        opening_message: RoleplayMessage;
      }>('/roleplay/start-session', body);

      setSession(data.session);
      setMessages([data.opening_message]);
      setPhase('conversation');
      connectWS(data.session.id);
    } catch {
      // ignore
    } finally {
      setStarting(false);
    }
  };

  // ── WebSocket ──
  const connectWS = useCallback((sessionId: string) => {
    const url = buildWSUrl(`/roleplay/${sessionId}`);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data);
      if (msg.event === 'roleplay.ai_reply') {
        setAiTyping(false);
        setMessages((prev) => [
          ...prev,
          {
            id: msg.data.id,
            session_id: sessionId,
            sender: 'ai',
            content: msg.data.content,
            created_at: msg.data.created_at,
          },
        ]);
      } else if (msg.event === 'roleplay.ended') {
        // Session ended, fetch report
        fetchReport(sessionId);
      }
    };
  }, []);

  const sendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !wsRef.current) return;

    const content = input.trim();
    const now = new Date().toISOString();

    // Optimistic user message
    setMessages((prev) => [
      ...prev,
      {
        id: `temp-${Date.now()}`,
        session_id: session?.id ?? '',
        sender: 'user',
        content,
        created_at: now,
      },
    ]);
    setInput('');
    setAiTyping(true);

    wsRef.current.send(JSON.stringify({ event: 'roleplay.message', data: { content } }));
  };

  const endSession = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ event: 'roleplay.end', data: {} }));
    }
  };

  const fetchReport = async (sessionId: string) => {
    if (timerRef.current) clearInterval(timerRef.current);
    setLoadingReport(true);
    setPhase('report');

    // Poll for evaluation (may take a few seconds for AI to finish)
    let retries = 0;
    const maxRetries = 15;
    while (retries < maxRetries) {
      try {
        const { data } = await api.get<RoleplayEvaluation>(`/roleplay/report/${sessionId}`);
        setEvaluation(data);
        setLoadingReport(false);
        return;
      } catch {
        retries++;
        await new Promise((r) => setTimeout(r, 2000));
      }
    }
    setLoadingReport(false);
  };

  const resetToSetup = () => {
    setPhase('setup');
    setSession(null);
    setMessages([]);
    setElapsed(0);
    setEvaluation(null);
    setSelectedScenario(null);
    setCustomTopic('');
    wsRef.current?.close();
    wsRef.current = null;
  };

  const formatTime = (sec: number) =>
    `${Math.floor(sec / 60)
      .toString()
      .padStart(2, '0')}:${(sec % 60).toString().padStart(2, '0')}`;

  const difficultyColors: Record<Difficulty, string> = {
    beginner: 'bg-green-100 text-green-700',
    intermediate: 'bg-yellow-100 text-yellow-700',
    advanced: 'bg-red-100 text-red-700',
  };

  // ── SETUP PHASE ──
  if (phase === 'setup') {
    return (
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-center gap-3">
          <Theater className="h-7 w-7 text-primary-600" />
          <h1 className="text-2xl font-bold">AI Role Play</h1>
        </div>

        {/* Tabs */}
        <div className="mb-6 flex gap-2">
          <button
            onClick={() => setTab('scenarios')}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
              tab === 'scenarios'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <Play className="mr-1.5 inline h-4 w-4" />
            Predefined Scenarios
          </button>
          <button
            onClick={() => {
              setTab('custom');
              setSelectedScenario(null);
            }}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
              tab === 'custom'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <Pen className="mr-1.5 inline h-4 w-4" />
            Custom Topic
          </button>
        </div>

        {/* Scenario selector */}
        {tab === 'scenarios' && (
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {scenarios.map((sc) => (
              <button
                key={sc.id}
                onClick={() => setSelectedScenario(sc)}
                className={`rounded-xl border-2 p-4 text-left transition ${
                  selectedScenario?.id === sc.id
                    ? 'border-primary-600 bg-primary-50'
                    : 'border-gray-200 bg-white hover:border-primary-300'
                }`}
              >
                <h3 className="mb-1 font-semibold">{sc.title}</h3>
                <p className="mb-2 text-sm text-gray-500">{sc.description}</p>
                <div className="flex flex-wrap gap-2 text-xs">
                  <span className="rounded-full bg-purple-100 px-2 py-0.5 text-purple-700">
                    {sc.ai_role}
                  </span>
                  <span className="rounded-full bg-blue-100 px-2 py-0.5 text-blue-700">
                    {sc.user_role}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 ${difficultyColors[sc.difficulty as Difficulty] ?? 'bg-gray-100 text-gray-600'}`}>
                    {sc.difficulty}
                  </span>
                </div>
              </button>
            ))}
            {scenarios.length === 0 && (
              <p className="col-span-full py-8 text-center text-gray-400">No scenarios available</p>
            )}
          </div>
        )}

        {/* Custom topic input */}
        {tab === 'custom' && (
          <div className="mb-6">
            <label className="mb-2 block text-sm font-medium text-gray-700">
              What would you like to talk about?
            </label>
            <input
              value={customTopic}
              onChange={(e) => setCustomTopic(e.target.value)}
              placeholder='e.g. "Discuss climate change", "Practice ordering food"'
              className="w-full rounded-lg border border-gray-300 px-4 py-3 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
              maxLength={200}
            />
          </div>
        )}

        {/* Difficulty selector */}
        <div className="mb-8">
          <label className="mb-2 block text-sm font-medium text-gray-700">Difficulty</label>
          <div className="flex gap-3">
            {(['beginner', 'intermediate', 'advanced'] as Difficulty[]).map((d) => (
              <button
                key={d}
                onClick={() => setDifficulty(d)}
                className={`rounded-lg px-5 py-2 text-sm font-medium capitalize transition ${
                  difficulty === d
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </div>

        {/* Start button */}
        <button
          onClick={startSession}
          disabled={starting || (!selectedScenario && !customTopic.trim())}
          className="flex items-center gap-2 rounded-lg bg-primary-600 px-8 py-3 font-medium text-white hover:bg-primary-700 disabled:opacity-50"
        >
          {starting ? 'Starting…' : 'Start Role Play'}
          {!starting && <ArrowRight className="h-4 w-4" />}
        </button>
      </div>
    );
  }

  // ── CONVERSATION PHASE ──
  if (phase === 'conversation') {
    return (
      <div className="flex h-[calc(100vh-6rem)] flex-col">
        {/* Header */}
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold">
              {selectedScenario?.title ?? customTopic ?? 'Role Play'}
            </h1>
            {selectedScenario && (
              <p className="text-sm text-gray-500">
                You: <span className="font-medium">{selectedScenario.user_role}</span> &middot; AI:{' '}
                <span className="font-medium">{selectedScenario.ai_role}</span>
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1 rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-700">
              <Clock className="h-4 w-4" />
              {formatTime(elapsed)}
            </span>
            <button
              onClick={endSession}
              className="flex items-center gap-1.5 rounded-lg bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-600"
            >
              <Square className="h-3.5 w-3.5" />
              End Session
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 space-y-3 overflow-y-auto rounded-xl bg-white p-4 shadow-sm">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[70%] rounded-2xl px-4 py-2 ${
                  msg.sender === 'user'
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-gray-800'
                }`}
              >
                <p className="text-sm">{msg.content}</p>
                <p
                  className={`mt-0.5 text-[10px] ${
                    msg.sender === 'user' ? 'text-primary-200' : 'text-gray-400'
                  }`}
                >
                  {new Date(msg.created_at).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </p>
              </div>
            </div>
          ))}
          {aiTyping && (
            <div className="flex justify-start">
              <div className="rounded-2xl bg-gray-100 px-4 py-2 text-sm text-gray-500">
                AI is typing…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <form onSubmit={sendMessage} className="mt-3 flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message…"
            className="flex-1 rounded-lg border border-gray-300 px-4 py-3 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            maxLength={5000}
          />
          <button
            type="submit"
            disabled={!input.trim()}
            className="rounded-lg bg-primary-600 px-4 text-white hover:bg-primary-700 disabled:opacity-50"
          >
            <Send className="h-5 w-5" />
          </button>
        </form>
      </div>
    );
  }

  // ── REPORT PHASE ──
  return (
    <div className="mx-auto max-w-3xl">
      <button
        onClick={resetToSetup}
        className="mb-4 flex items-center gap-1 text-sm text-primary-600 hover:underline"
      >
        <ChevronLeft className="h-4 w-4" />
        New Role Play
      </button>

      {loadingReport ? (
        <div className="flex flex-col items-center py-24 text-gray-400">
          <div className="mb-4 h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
          <p>Analyzing your conversation…</p>
        </div>
      ) : evaluation ? (
        <>
          {/* Overall score */}
          <div className="mb-6 flex items-center gap-6 rounded-xl bg-white p-6 shadow-sm">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary-100">
              <span className="text-3xl font-bold text-primary-700">
                {evaluation.overall_score.toFixed(0)}
              </span>
            </div>
            <div>
              <h2 className="text-lg font-bold">Overall Score</h2>
              <p className="text-sm text-gray-500">
                +{evaluation.xp_earned} XP earned
              </p>
            </div>
          </div>

          {/* Dimension scores */}
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(
              [
                ['Fluency', evaluation.fluency],
                ['Grammar', evaluation.grammar],
                ['Vocabulary', evaluation.vocabulary],
                ['Confidence', evaluation.confidence],
                ['Clarity', evaluation.clarity],
                ['Relevance', evaluation.relevance],
                ['Consistency', evaluation.consistency],
              ] as [string, number][]
            ).map(([label, score]) => (
              <div key={label} className="rounded-xl bg-white p-4 text-center shadow-sm">
                <p className="mb-1 text-xs text-gray-500">{label}</p>
                <p className="text-2xl font-bold text-primary-700">{score}</p>
              </div>
            ))}
          </div>

          {/* Strengths */}
          {evaluation.strengths.length > 0 && (
            <div className="mb-4 rounded-xl bg-green-50 p-5">
              <h3 className="mb-2 flex items-center gap-2 font-semibold text-green-800">
                <TrendingUp className="h-4 w-4" />
                Strengths
              </h3>
              <ul className="space-y-1 text-sm text-green-700">
                {evaluation.strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <Star className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Weaknesses */}
          {evaluation.weaknesses.length > 0 && (
            <div className="mb-4 rounded-xl bg-yellow-50 p-5">
              <h3 className="mb-2 flex items-center gap-2 font-semibold text-yellow-800">
                <TrendingDown className="h-4 w-4" />
                Areas to Improve
              </h3>
              <ul className="space-y-1 text-sm text-yellow-700">
                {evaluation.weaknesses.map((w, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="mt-0.5">•</span>
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Suggestions */}
          {evaluation.improvement_suggestions.length > 0 && (
            <div className="mb-4 rounded-xl bg-blue-50 p-5">
              <h3 className="mb-2 flex items-center gap-2 font-semibold text-blue-800">
                <Lightbulb className="h-4 w-4" />
                Improvement Tips
              </h3>
              <ul className="space-y-1 text-sm text-blue-700">
                {evaluation.improvement_suggestions.map((s, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="mt-0.5">{i + 1}.</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Filler words */}
          {Object.keys(evaluation.filler_words).length > 0 && (
            <div className="rounded-xl bg-gray-50 p-5">
              <h3 className="mb-2 font-semibold text-gray-700">Filler Words Detected</h3>
              <div className="flex flex-wrap gap-2">
                {Object.entries(evaluation.filler_words).map(([word, count]) => (
                  <span
                    key={word}
                    className="rounded-full bg-gray-200 px-3 py-1 text-sm text-gray-700"
                  >
                    "{word}" &times; {count}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <p className="py-12 text-center text-gray-400">
          Could not load evaluation report. Please try again.
        </p>
      )}
    </div>
  );
}

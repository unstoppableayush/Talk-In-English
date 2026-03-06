import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { useSessionSocket } from '@/hooks/useSessionSocket';
import { useRoomStore } from '@/stores/roomStore';
import type { Room, Participant } from '@/types';
import {
  Hand,
  Mic,
  MicOff,
  SendHorizontal,
  Timer,
  Users,
  LogOut,
} from 'lucide-react';

export default function PublicRoomPage() {
  const { roomId } = useParams<{ roomId: string }>();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [role, setRole] = useState<'speaker' | 'listener'>('speaker');
  const [input, setInput] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [muted, setMuted] = useState(false);
  const store = useRoomStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: room } = useQuery<Room>({
    queryKey: ['room', roomId],
    queryFn: () => api.get(`/rooms/${roomId}`).then((r) => r.data),
    enabled: !!roomId,
  });

  const { data: participants } = useQuery<Participant[]>({
    queryKey: ['participants', roomId],
    queryFn: () => api.get(`/rooms/${roomId}/participants`).then((r) => r.data),
    enabled: !!roomId,
    refetchInterval: 5000,
  });

  const { sendMessage, raiseHand, promote } = useSessionSocket(sessionId, role);

  // Timer
  useEffect(() => {
    if (!sessionId) return;
    const interval = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(interval);
  }, [sessionId]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [store.messages]);

  // Cleanup
  useEffect(() => {
    return () => store.reset();
  }, []);

  const joinRoom = async (asRole: 'speaker' | 'listener') => {
    if (!roomId) return;
    setRole(asRole);
    try {
      const { data } = await api.post(`/rooms/${roomId}/join`, { role: asRole });
      setSessionId(data.session_id);
    } catch {
      // ignore
    }
  };

  const leaveRoom = async () => {
    if (!roomId) return;
    await api.post(`/rooms/${roomId}/leave`).catch(() => {});
    store.reset();
    setSessionId(null);
  };

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    sendMessage(input.trim());
    setInput('');
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const speakers = participants?.filter((p) => p.role === 'speaker') ?? [];
  const listeners = participants?.filter((p) => p.role === 'listener') ?? [];

  // ---------- Pre-join screen ----------
  if (!sessionId) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <h1 className="mb-2 text-2xl font-bold">{room?.name ?? 'Public Room'}</h1>
        <p className="mb-1 text-gray-500">{room?.topic ?? 'General discussion'}</p>
        <p className="mb-8 text-sm text-gray-400">
          {room?.speaker_count ?? 0}/{room?.max_speakers ?? 5} speakers · {room?.listener_count ?? 0} listeners
        </p>
        <div className="flex gap-3">
          <button
            onClick={() => joinRoom('speaker')}
            className="rounded-lg bg-primary-600 px-6 py-3 font-medium text-white hover:bg-primary-700"
          >
            Join as Speaker
          </button>
          <button
            onClick={() => joinRoom('listener')}
            className="rounded-lg border border-primary-600 px-6 py-3 font-medium text-primary-600 hover:bg-primary-50"
          >
            Join as Listener
          </button>
        </div>
      </div>
    );
  }

  // ---------- Room UI ----------
  return (
    <div className="flex h-[calc(100vh-6rem)] gap-4">
      {/* Main area */}
      <div className="flex flex-1 flex-col">
        {/* Header */}
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold">{room?.name}</h1>
            <p className="text-sm text-gray-500">{room?.topic}</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1 text-sm text-gray-500">
              <Timer className="h-4 w-4" />
              {formatTime(elapsed)}
            </div>
            <button
              onClick={leaveRoom}
              className="flex items-center gap-1 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-100"
            >
              <LogOut className="h-4 w-4" />
              Leave
            </button>
          </div>
        </div>

        {/* Speaker slots */}
        <div className="mb-3 grid grid-cols-5 gap-2">
          {Array.from({ length: room?.max_speakers ?? 5 }).map((_, i) => {
            const speaker = speakers[i];
            return (
              <div
                key={i}
                className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-4 text-center ${
                  speaker ? 'border-primary-300 bg-primary-50' : 'border-gray-200 bg-gray-50'
                }`}
              >
                <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary-200 text-lg font-bold text-primary-700">
                  {speaker ? speaker.user_id.slice(0, 2).toUpperCase() : '?'}
                </div>
                <p className="text-xs font-medium truncate w-full">
                  {speaker ? `Speaker ${i + 1}` : 'Empty'}
                </p>
                {speaker && (
                  <div className="mt-1 flex items-center gap-1">
                    <Mic className="h-3 w-3 text-green-500" />
                    <span className="text-[10px] text-green-600">Live</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* AI Moderator bar */}
        {store.messages.filter((m) => m.message_type === 'moderation').length > 0 && (
          <div className="mb-3 rounded-lg bg-yellow-50 p-3 text-sm text-yellow-800">
            <span className="font-medium">AI Moderator: </span>
            {store.messages.filter((m) => m.message_type === 'moderation').at(-1)?.content}
          </div>
        )}

        {/* Live transcript */}
        <div className="flex-1 space-y-2 overflow-y-auto rounded-xl bg-white p-4 shadow-sm">
          {store.messages
            .filter((m) => m.message_type !== 'moderation')
            .map((msg) => (
              <div key={msg.id} className="flex gap-2 text-sm">
                <span className="font-medium text-primary-600">
                  {msg.sender_type === 'ai' ? 'AI' : msg.sender_name}:
                </span>
                <span className="text-gray-700">{msg.content}</span>
              </div>
            ))}
          <div ref={bottomRef} />
        </div>

        {/* Input (speakers only) */}
        {role === 'speaker' && (
          <form onSubmit={handleSend} className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => setMuted(!muted)}
              className={`rounded-xl p-3 ${
                muted ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-600'
              }`}
            >
              {muted ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
            </button>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type a message…"
              className="flex-1 rounded-xl border px-4 py-3 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
            <button
              type="submit"
              className="rounded-xl bg-primary-600 px-4 text-white hover:bg-primary-700"
            >
              <SendHorizontal className="h-5 w-5" />
            </button>
          </form>
        )}

        {/* Raise hand (listeners) */}
        {role === 'listener' && (
          <div className="mt-3 flex justify-center">
            <button
              onClick={raiseHand}
              className="flex items-center gap-2 rounded-xl bg-yellow-100 px-6 py-3 font-medium text-yellow-800 hover:bg-yellow-200"
            >
              <Hand className="h-5 w-5" />
              Raise Hand
            </button>
          </div>
        )}
      </div>

      {/* Sidebar — Listeners */}
      <aside className="w-56 shrink-0 rounded-xl bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-700">
          <Users className="h-4 w-4" />
          Listeners ({listeners.length})
        </div>
        <div className="space-y-2">
          {listeners.map((l) => (
            <div
              key={l.id}
              className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-sm"
            >
              <span className="truncate">{l.user_id.slice(0, 8)}</span>
              <div className="flex items-center gap-1">
                {l.hand_raised && <Hand className="h-3 w-3 text-yellow-500" />}
                {role === 'speaker' && l.hand_raised && (
                  <button
                    onClick={() => promote(l.user_id)}
                    className="ml-1 text-xs text-primary-600 hover:underline"
                  >
                    Promote
                  </button>
                )}
              </div>
            </div>
          ))}
          {listeners.length === 0 && (
            <p className="text-xs text-gray-400">No listeners yet</p>
          )}
        </div>
      </aside>
    </div>
  );
}

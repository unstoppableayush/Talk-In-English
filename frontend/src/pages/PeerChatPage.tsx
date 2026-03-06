import { useEffect, useRef, useState } from 'react';
import api from '@/lib/api';
import { useSessionSocket } from '@/hooks/useSessionSocket';
import { useRoomStore } from '@/stores/roomStore';
import { SendHorizontal } from 'lucide-react';

export default function PeerChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [starting, setStarting] = useState(false);
  const store = useRoomStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  const { sendMessage } = useSessionSocket(sessionId, 'speaker');

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [store.messages]);

  useEffect(() => {
    return () => store.reset();
  }, []);

  const startSession = async () => {
    setStarting(true);
    try {
      const { data: room } = await api.post('/rooms', {
        name: 'Peer Practice',
        room_type: 'private',
        topic: 'Conversation practice',
      });
      const { data: session } = await api.post(`/rooms/${room.id}/join`, { role: 'speaker' });
      setSessionId(session.session_id);
    } catch {
      // ignore
    } finally {
      setStarting(false);
    }
  };

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    sendMessage(input.trim());
    setInput('');
  };

  if (!sessionId) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <h1 className="mb-4 text-2xl font-bold">Peer Chat</h1>
        <p className="mb-8 text-gray-500">
          Practice 1-on-1 with another speaker. AI monitors silently and gives feedback after.
        </p>
        <button
          onClick={startSession}
          disabled={starting}
          className="rounded-lg bg-primary-600 px-8 py-3 font-medium text-white hover:bg-primary-700 disabled:opacity-50"
        >
          {starting ? 'Creating room…' : 'Start Peer Session'}
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-6rem)] flex-col">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">Peer Chat</h1>
        <div className="flex gap-3 text-sm text-gray-500">
          <span>{store.speakerCount} speaker(s)</span>
          <span className="text-xs text-green-500">● AI monitoring</span>
        </div>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto rounded-xl bg-white p-4 shadow-sm">
        {store.messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.sender_type === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[70%] rounded-2xl px-4 py-2 ${
                msg.sender_type === 'user'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-800'
              }`}
            >
              <p className="mb-0.5 text-xs opacity-70">{msg.sender_name}</p>
              <p className="text-sm">{msg.content}</p>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} className="mt-3 flex gap-2">
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
    </div>
  );
}

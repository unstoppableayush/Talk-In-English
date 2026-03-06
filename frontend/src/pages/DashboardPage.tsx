import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import api from '@/lib/api';
import type { Dashboard, Room } from '@/types';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { MessageSquare, Users, Zap, Flame } from 'lucide-react';

export default function DashboardPage() {
  const navigate = useNavigate();

  const { data: dashboard } = useQuery<Dashboard>({
    queryKey: ['dashboard'],
    queryFn: () => api.get('/progress/dashboard').then((r) => r.data),
  });

  const { data: rooms } = useQuery<Room[]>({
    queryKey: ['rooms'],
    queryFn: () => api.get('/rooms').then((r) => r.data),
  });

  const latest = dashboard?.snapshots?.['all'];
  const chartData = latest
    ? [
        { name: 'Fluency', score: latest.fluency ?? 0 },
        { name: 'Clarity', score: latest.clarity ?? 0 },
        { name: 'Grammar', score: latest.grammar ?? 0 },
        { name: 'Vocabulary', score: latest.vocabulary ?? 0 },
        { name: 'Coherence', score: latest.coherence ?? 0 },
        { name: 'Engagement', score: latest.engagement ?? 0 },
      ]
    : [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Zap} label="Total XP" value={dashboard?.xp ?? 0} />
        <StatCard icon={Flame} label="Streak" value={`${dashboard?.streak_days ?? 0} days`} />
        <StatCard icon={MessageSquare} label="Sessions" value={dashboard?.total_sessions ?? 0} />
        <StatCard icon={Users} label="Practice" value={`${dashboard?.total_practice_minutes ?? 0} min`} />
      </div>

      {/* Score chart */}
      {chartData.length > 0 && (
        <div className="rounded-xl bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">Skill Breakdown</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Bar dataKey="score" fill="#6366f1" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Active rooms */}
      <div className="rounded-xl bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold">Public Rooms</h2>
        {rooms && rooms.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {rooms.filter((r) => r.is_active).map((room) => (
              <button
                key={room.id}
                onClick={() => navigate(`/room/${room.id}`)}
                className="rounded-lg border border-gray-200 p-4 text-left transition hover:border-primary-300 hover:shadow-md"
              >
                <h3 className="font-medium">{room.name}</h3>
                <p className="mt-1 text-sm text-gray-500">{room.topic || 'General'}</p>
                <div className="mt-2 flex gap-3 text-xs text-gray-400">
                  <span>{room.speaker_count}/{room.max_speakers} speakers</span>
                  <span>{room.listener_count} listeners</span>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500">No active rooms. Create one to get started!</p>
        )}
      </div>

      {/* Quick actions */}
      <div className="flex gap-3">
        <button
          onClick={() => navigate('/ai-chat')}
          className="rounded-lg bg-primary-600 px-6 py-3 font-medium text-white hover:bg-primary-700"
        >
          Start AI Conversation
        </button>
        <button
          onClick={() => navigate('/peer-chat')}
          className="rounded-lg border border-primary-600 px-6 py-3 font-medium text-primary-600 hover:bg-primary-50"
        >
          Find Peer to Practice
        </button>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
}) {
  return (
    <div className="flex items-center gap-4 rounded-xl bg-white p-5 shadow-sm">
      <div className="rounded-lg bg-primary-100 p-3">
        <Icon className="h-5 w-5 text-primary-600" />
      </div>
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className="text-xl font-bold">{value}</p>
      </div>
    </div>
  );
}

import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { SessionScore, AIFeedback } from '@/types';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from 'recharts';
import { Award, ChevronLeft, TrendingUp, Lightbulb, Dumbbell } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function ScoreReportPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const { data: score, isLoading: scoreLoading } = useQuery<SessionScore>({
    queryKey: ['score', sessionId],
    queryFn: () => api.get(`/evaluations/sessions/${sessionId}/score`).then((r) => r.data),
    enabled: !!sessionId,
  });

  const { data: feedback, isLoading: feedbackLoading } = useQuery<AIFeedback>({
    queryKey: ['feedback', sessionId],
    queryFn: () => api.get(`/evaluations/sessions/${sessionId}/feedback`).then((r) => r.data),
    enabled: !!sessionId,
  });

  const isLoading = scoreLoading || feedbackLoading;

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  if (!score) {
    return (
      <div className="py-24 text-center text-gray-500">
        Score not available yet. The AI is still evaluating your session.
      </div>
    );
  }

  const radarData = [
    { dim: 'Fluency', value: score.fluency },
    { dim: 'Clarity', value: score.clarity },
    { dim: 'Grammar', value: score.grammar },
    { dim: 'Vocabulary', value: score.vocabulary },
    { dim: 'Coherence', value: score.coherence },
    { dim: 'Leadership', value: score.leadership },
    { dim: 'Engagement', value: score.engagement },
    { dim: 'Turn-Taking', value: score.turn_taking },
  ];

  const barData = radarData.map((d) => ({ ...d, fill: d.value >= 70 ? '#4f46e5' : '#f59e0b' }));

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
      >
        <ChevronLeft className="h-4 w-4" /> Back
      </button>

      {/* Overall */}
      <div className="flex items-center gap-6 rounded-xl bg-white p-6 shadow-sm">
        <div className="flex h-24 w-24 items-center justify-center rounded-full bg-primary-100 text-3xl font-bold text-primary-600">
          {score.overall}
        </div>
        <div>
          <h1 className="text-xl font-bold">Session Score</h1>
          <p className="text-gray-500">Overall performance</p>
          <div className="mt-1 flex items-center gap-2 text-sm">
            <Award className="h-4 w-4 text-yellow-500" />
            <span className="font-medium text-yellow-600">+{score.xp_earned} XP earned</span>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-4">
        {/* Radar */}
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <h2 className="mb-3 font-semibold">Skill Radar</h2>
          <ResponsiveContainer width="100%" height={250}>
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="dim" tick={{ fontSize: 11 }} />
              <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
              <Radar dataKey="value" stroke="#4f46e5" fill="#4f46e5" fillOpacity={0.25} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Bar */}
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <h2 className="mb-3 font-semibold">Dimension Breakdown</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={barData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" domain={[0, 100]} />
              <YAxis type="category" dataKey="dim" width={80} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* AI Feedback */}
      {feedback && (
        <div className="space-y-4">
          <div className="rounded-xl bg-white p-5 shadow-sm">
            <h2 className="mb-2 font-semibold">Summary</h2>
            <p className="text-sm text-gray-700">{feedback.summary}</p>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-xl bg-green-50 p-4">
              <div className="mb-2 flex items-center gap-2 font-medium text-green-700">
                <TrendingUp className="h-4 w-4" /> Strengths
              </div>
              <ul className="space-y-1 text-sm text-green-800">
                {(feedback.strengths as string[]).map((s, i) => (
                  <li key={i}>• {s}</li>
                ))}
              </ul>
            </div>

            <div className="rounded-xl bg-yellow-50 p-4">
              <div className="mb-2 flex items-center gap-2 font-medium text-yellow-700">
                <Lightbulb className="h-4 w-4" /> Improvement Areas
              </div>
              <ul className="space-y-1 text-sm text-yellow-800">
                {(feedback.improvement_areas as string[]).map((s, i) => (
                  <li key={i}>• {s}</li>
                ))}
              </ul>
            </div>

            <div className="rounded-xl bg-primary-50 p-4">
              <div className="mb-2 flex items-center gap-2 font-medium text-primary-700">
                <Dumbbell className="h-4 w-4" /> Suggested Exercises
              </div>
              <ul className="space-y-1 text-sm text-primary-800">
                {(feedback.suggested_exercises as string[]).map((s, i) => (
                  <li key={i}>• {s}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

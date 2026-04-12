import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Row, Col, Typography, Button, Spin, Tag, Space, Alert } from 'antd';
import { ArrowLeftOutlined, TrophyOutlined, RiseOutlined, BulbOutlined, ExperimentOutlined } from '@ant-design/icons';
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

const { Title, Text, Paragraph } = Typography;

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
      <div className="flex h-[60vh] items-center justify-center flex-col gap-4">
        <Spin size="large" />
        <Text type="secondary">Generating detailed AI feedback...</Text>
      </div>
    );
  }

  if (!score) {
    return (
      <div className="py-24 text-center">
        <Alert
          message="Evaluation In Progress"
          description="Score not available yet. The AI is still evaluating your session. Please check back in a few minutes."
          type="info"
          showIcon
          className="max-w-md mx-auto"
        />
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
    <div className="mx-auto max-w-5xl space-y-6 pb-12">
      {/* Back Header */}
      <div className="flex items-center gap-4 mb-2">
        <Button 
          type="text" 
          icon={<ArrowLeftOutlined />} 
          onClick={() => navigate(-1)}
          className="text-gray-500 hover:text-gray-800"
        >
          Back to Dashboard
        </Button>
      </div>

      {/* Overall Score Card */}
      <Card bordered={false} className="shadow-sm rounded-2xl overflow-hidden bg-gradient-to-r from-indigo-50 to-white">
        <div className="flex items-center gap-8">
          <div className="relative">
            <svg className="w-32 h-32 transform -rotate-90">
              <circle
                cx="64"
                cy="64"
                r="56"
                stroke="currentColor"
                strokeWidth="12"
                fill="transparent"
                className="text-indigo-100"
              />
              <circle
                cx="64"
                cy="64"
                r="56"
                stroke="currentColor"
                strokeWidth="12"
                fill="transparent"
                strokeDasharray={56 * 2 * Math.PI}
                strokeDashoffset={56 * 2 * Math.PI - (score.overall / 100) * 56 * 2 * Math.PI}
                className="text-indigo-600 transition-all duration-1000 ease-out"
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-3xl font-bold text-indigo-700">{score.overall}</span>
            </div>
          </div>
          <div>
            <Title level={2} className="!mb-1">Session Score</Title>
            <Text type="secondary" className="text-lg block mb-3">Overall performance analysis</Text>
            <Tag color="gold" icon={<TrophyOutlined />} className="px-3 py-1 text-sm border-yellow-300 bg-yellow-50 text-yellow-700">
              +{score.xp_earned} XP earned
            </Tag>
          </div>
        </div>
      </Card>

      {/* Charts */}
      <Row gutter={[24, 24]}>
        {/* Radar */}
        <Col xs={24} md={12}>
          <Card bordered={false} className="shadow-sm rounded-xl h-full" title={<><RiseOutlined className="mr-2 text-indigo-500"/> Skill Radar</>}>
            <ResponsiveContainer width="100%" height={300}>
              <RadarChart data={radarData} margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
                <PolarGrid stroke="#e5e7eb" />
                <PolarAngleAxis dataKey="dim" tick={{ fill: '#6b7280', fontSize: 12 }} />
                <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                <Radar dataKey="value" stroke="#4f46e5" strokeWidth={2} fill="#4f46e5" fillOpacity={0.4} />
                <Tooltip 
                  contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        {/* Bar */}
        <Col xs={24} md={12}>
          <Card bordered={false} className="shadow-sm rounded-xl h-full" title={<><RiseOutlined className="mr-2 text-indigo-500"/> Dimension Breakdown</>}>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={barData} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f3f4f6" />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="dim" width={85} tick={{ fill: '#4b5563', fontSize: 12, fontWeight: 500 }} axisLine={false} tickLine={false} />
                <Tooltip 
                  cursor={{ fill: '#f9fafb' }}
                  contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={16}>
                   {/* Tooltip already handles hover, recharts cell coloring handled by data */}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      {/* AI Feedback */}
      {feedback && (
        <div className="space-y-6 mt-8">
          <Title level={4} className="!mb-0">Detailed AI Analysis</Title>
          <Card bordered={false} className="shadow-sm rounded-xl bg-white">
            <Title level={5} className="!mb-3 !text-gray-700">Executive Summary</Title>
            <Paragraph className="text-gray-600 text-base leading-relaxed">
              {feedback.summary}
            </Paragraph>
          </Card>

          <Row gutter={[16, 16]}>
            <Col xs={24} md={8}>
              <Card bordered={false} className="shadow-sm rounded-xl h-full border-t-4 border-t-green-500 bg-green-50/30">
                <Space className="mb-4 text-green-700 font-semibold text-lg w-full pb-2 border-b border-green-100">
                  <RiseOutlined /> Strengths
                </Space>
                <ul className="space-y-3 m-0 pl-0 list-none">
                  {(feedback.strengths as string[]).map((s, i) => (
                    <li key={i} className="flex items-start text-sm text-green-800">
                      <span className="mr-2 text-green-500 mt-0.5">•</span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            </Col>

            <Col xs={24} md={8}>
              <Card bordered={false} className="shadow-sm rounded-xl h-full border-t-4 border-t-yellow-500 bg-yellow-50/30">
                <Space className="mb-4 text-yellow-700 font-semibold text-lg w-full pb-2 border-b border-yellow-100">
                  <BulbOutlined /> Areas to Improve
                </Space>
                <ul className="space-y-3 m-0 pl-0 list-none">
                  {(feedback.improvement_areas as string[]).map((s, i) => (
                    <li key={i} className="flex items-start text-sm text-yellow-800">
                      <span className="mr-2 text-yellow-500 mt-0.5">•</span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            </Col>

            <Col xs={24} md={8}>
              <Card bordered={false} className="shadow-sm rounded-xl h-full border-t-4 border-t-indigo-500 bg-indigo-50/30">
                <Space className="mb-4 text-indigo-700 font-semibold text-lg w-full pb-2 border-b border-indigo-100">
                  <ExperimentOutlined /> Suggested Exercises
                </Space>
                <ul className="space-y-3 m-0 pl-0 list-none">
                  {(feedback.suggested_exercises as string[]).map((s, i) => (
                    <li key={i} className="flex items-start text-sm text-indigo-800">
                      <span className="mr-2 text-indigo-500 mt-0.5">•</span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            </Col>
          </Row>

          {feedback.dimension_feedback && Object.keys(feedback.dimension_feedback).length > 0 && (
            <Card bordered={false} className="shadow-sm rounded-xl">
              <Title level={5} className="!mb-4 !text-gray-700">Dimension-Level Feedback</Title>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(feedback.dimension_feedback).map(([dimension, note]) => (
                  <div key={dimension} className="rounded-lg border border-gray-100 bg-gray-50 p-4">
                    <Text strong className="capitalize text-gray-700">{dimension.split('_').join(' ')}</Text>
                    <Paragraph className="!mb-0 !mt-2 text-gray-600 text-sm leading-relaxed">
                      {note}
                    </Paragraph>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

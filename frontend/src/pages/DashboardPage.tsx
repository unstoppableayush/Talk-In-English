import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, Statistic, Button, Typography, Space, Empty } from 'antd';
import {
  MessageOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  FireOutlined,
  RobotOutlined,
  SearchOutlined
} from '@ant-design/icons';
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

const { Title, Text } = Typography;

export default function DashboardPage() {
  const navigate = useNavigate();

  const { data: dashboard, isLoading: isDashboardLoading } = useQuery<Dashboard>({
    queryKey: ['dashboard'],
    queryFn: () => api.get('/progress/dashboard').then((r) => r.data),
  });

  const { data: rooms, isLoading: isRoomsLoading } = useQuery<Room[]>({
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

  const activeRooms = rooms?.filter((r) => r.is_active) || [];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <Space className="w-full justify-between mb-4">
        <Title level={2} className="!mb-0">Dashboard</Title>
        <Space>
          <Button type="primary" icon={<RobotOutlined />} onClick={() => navigate('/ai-chat')} size="large" className="bg-indigo-600">
            Start AI Conversation
          </Button>
          <Button icon={<SearchOutlined />} onClick={() => navigate('/peer-chat')} size="large">
            Find Peer
          </Button>
        </Space>
      </Space>

      {/* Stats cards */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card bordered={false} className="shadow-sm">
            <Statistic 
              title="Total XP" 
              value={dashboard?.xp ?? 0} 
              prefix={<ThunderboltOutlined className="text-yellow-500" />} 
              loading={isDashboardLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card bordered={false} className="shadow-sm">
            <Statistic 
              title="Streak" 
              value={dashboard?.streak_days ?? 0} 
              suffix="days"
              prefix={<FireOutlined className="text-red-500" />} 
              loading={isDashboardLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card bordered={false} className="shadow-sm">
            <Statistic 
              title="Sessions" 
              value={dashboard?.total_sessions ?? 0} 
              prefix={<MessageOutlined className="text-indigo-500" />} 
              loading={isDashboardLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card bordered={false} className="shadow-sm">
            <Statistic 
              title="Practice" 
              value={dashboard?.total_practice_minutes ?? 0} 
              suffix="min"
              prefix={<TeamOutlined className="text-green-500" />} 
              loading={isDashboardLoading}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} className="mt-6">
        {/* Score chart */}
        <Col xs={24} lg={16}>
          <Card title="Skill Breakdown" bordered={false} className="shadow-sm h-full">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: 'rgba(99, 102, 241, 0.1)' }} />
                  <Bar dataKey="score" fill="#6366f1" radius={[4, 4, 0, 0]} barSize={40} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Empty description="No session data yet" className="mt-12" />
            )}
          </Card>
        </Col>

        {/* Active rooms */}
        <Col xs={24} lg={8}>
          <Card title="Public Rooms" bordered={false} className="shadow-sm h-full" loading={isRoomsLoading}>
            {activeRooms.length > 0 ? (
              <div className="flex flex-col gap-3">
                {activeRooms.map((room) => (
                  <Card.Grid 
                    key={room.id} 
                    className="w-full rounded-lg cursor-pointer hover:shadow-md transition-shadow p-4 bg-gray-50 hover:bg-white border hover:border-indigo-300"
                    onClick={() => navigate(`/room/${room.id}`)}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <Text strong className="block text-indigo-900">{room.name}</Text>
                        <Text type="secondary" className="text-xs block mb-2">{room.topic || 'General'}</Text>
                      </div>
                    </div>
                    <Space size="middle" className="text-xs text-gray-500">
                      <span><TeamOutlined /> {room.speaker_count}/{room.max_speakers} speakers</span>
                      <span><MessageOutlined /> {room.listener_count} list</span>
                    </Space>
                  </Card.Grid>
                ))}
              </div>
            ) : (
              <Empty description="No active rooms" className="mt-8">
                <Button type="dashed" onClick={() => navigate('/room/new')}>Create One</Button>
              </Empty>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

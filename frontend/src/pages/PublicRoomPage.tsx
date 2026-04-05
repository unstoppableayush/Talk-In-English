import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Layout, Button, Typography, Avatar, Tag, Space, Alert, Tooltip, Row, Col, Badge, List, Card, Segmented } from 'antd';
import {
  SoundOutlined,
  AudioOutlined,
  AudioMutedOutlined,
  ClockCircleOutlined,
  TeamOutlined,
  LogoutOutlined,
  RobotOutlined,
  UserOutlined,
  CrownOutlined
} from '@ant-design/icons';
import api from '@/lib/api';
import { useSessionSocket } from '@/hooks/useSessionSocket';
import { useAudioSocket, type SttMode } from '@/hooks/useAudioSocket';
import { useRoomStore } from '@/stores/roomStore';
import type { Room, Participant } from '@/types';

const { Title, Text } = Typography;
const { Content, Sider } = Layout;

export default function PublicRoomPage() {
  const { roomId } = useParams<{ roomId: string }>();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [role, setRole] = useState<'speaker' | 'listener'>('speaker');
  const [elapsed, setElapsed] = useState(0);
  const [sttMode, setSttMode] = useState<SttMode>('browser');
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
  
  // Audio Socket connects for both; speakers can record.
  const { startRecording, stopRecording, isRecording, isConnecting } = useAudioSocket(sessionId, {
    mode: sttMode,
    onResult: (text) => {
      if (text) sendMessage(text);
    },
  });

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

  const handleMouseDown = () => startRecording();
  const handleMouseUp = () => stopRecording();

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
      <div className="flex flex-col items-center justify-center py-24 text-center px-4">
        <TeamOutlined className="text-6xl text-indigo-500 mb-6" />
        <Title level={2} className="!mb-2">{room?.name ?? 'Public Room'}</Title>
        <Text className="text-gray-500 text-lg mb-2">{room?.topic ?? 'General discussion'}</Text>
        <Space className="mb-8" split={<Text type="secondary">•</Text>}>
          <Text type="secondary">{room?.speaker_count ?? 0}/{room?.max_speakers ?? 5} speakers</Text>
          <Text type="secondary">{room?.listener_count ?? 0} listeners</Text>
        </Space>
        
        <Space size="middle" className="flex-col sm:flex-row">
          <Button
            type="primary"
            size="large"
            icon={<SoundOutlined />}
            onClick={() => joinRoom('speaker')}
            className="bg-indigo-600 w-full sm:w-auto px-8 rounded-full shadow-lg hover:shadow-xl transition-all h-12 text-base"
          >
            Join as Speaker
          </Button>
          <Button
            size="large"
            icon={<UserOutlined />}
            onClick={() => joinRoom('listener')}
            className="w-full sm:w-auto px-8 rounded-full border-indigo-600 text-indigo-600 hover:text-indigo-700 hover:border-indigo-700 h-12 text-base"
          >
            Join as Listener
          </Button>
        </Space>
      </div>
    );
  }

  const modMessages = store.messages.filter((m) => m.message_type === 'moderation');
  const moderatorMessage = modMessages[modMessages.length - 1];
  const chatMessages = store.messages.filter((m) => m.message_type !== 'moderation');

  // ---------- Room UI ----------
  return (
    <Layout className="bg-transparent h-[calc(100vh-6rem)]">
      <Layout className="bg-transparent pr-4 gap-4 flex flex-row">
        {/* Main Area */}
        <Content className="flex flex-col flex-1 max-w-5xl rounded-2xl bg-white shadow-sm border border-gray-100 overflow-hidden">
          {/* Header */}
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50">
            <div>
              <Title level={4} className="!mb-0 whitespace-nowrap overflow-hidden text-ellipsis max-w-[200px] sm:max-w-md">{room?.name}</Title>
              <Text type="secondary" className="text-sm">{room?.topic}</Text>
            </div>
            <Space size="large">
              <Segmented
                size="small"
                value={sttMode}
                onChange={(v) => setSttMode(v as SttMode)}
                options={[
                  { label: 'Browser STT', value: 'browser' },
                  { label: 'Deepgram STT', value: 'deepgram' },
                ]}
              />
              <Tag icon={<ClockCircleOutlined />} color="default" className="text-sm border-0 bg-transparent flex items-center gap-1 text-gray-500">
                {formatTime(elapsed)}
              </Tag>
              <Button danger type="text" icon={<LogoutOutlined />} onClick={leaveRoom} className="hover:bg-red-50 text-red-500 rounded-lg font-medium">
                Leave
              </Button>
            </Space>
          </div>

          <div className="p-6 flex-1 flex flex-col overflow-y-auto bg-gray-50/30">
            {/* Speaker Slots */}
            <div className="mb-6">
              <Text strong className="block mb-3 text-gray-500 uppercase text-xs tracking-wider">Speakers Stage</Text>
              <Row gutter={[12, 12]} justify="start">
                {Array.from({ length: room?.max_speakers ?? 5 }).map((_, i) => {
                  const speaker = speakers[i];
                  return (
                    <Col xs={12} sm={8} md={6} lg={4} key={i}>
                      <Card 
                        size="small"
                        bordered={false}
                        className={`text-center h-full border-2 ${speaker ? 'border-indigo-200 bg-indigo-50/50' : 'border-dashed border-gray-200 bg-gray-50'}`}
                        styles={{ body: { padding: '16px 8px', display: 'flex', flexDirection: 'column', alignItems: 'center' } }}
                      >
                        <Badge dot={!!speaker} color="green" offset={[-5, 5]}>
                          <Avatar size={48} className={`mb-2 font-bold ${speaker ? 'bg-indigo-500' : 'bg-gray-200 text-gray-400'}`}>
                            {speaker ? speaker.user_id.slice(0, 2).toUpperCase() : '?'}
                          </Avatar>
                        </Badge>
                        <Text strong className="text-xs truncate w-full block text-gray-800">
                          {speaker ? `Speaker ${i + 1}` : 'Empty'}
                        </Text>
                        {speaker && (
                          <Tag bordered={false} color="success" className="mt-1 text-[10px] items-center flex gap-1 m-0">
                            <SoundOutlined /> Live
                          </Tag>
                        )}
                      </Card>
                    </Col>
                  );
                })}
              </Row>
            </div>

            {/* AI Moderator Alert */}
            {moderatorMessage && (
              <Alert
                message={<Space><CrownOutlined /> AI Moderator</Space>}
                description={moderatorMessage.content}
                type="warning"
                showIcon
                className="mb-4 rounded-xl border-yellow-200 bg-yellow-50"
              />
            )}

            {/* Live Chat Feed */}
            <div className="flex-1 bg-white border border-gray-100 rounded-xl p-4 overflow-y-auto space-y-3 shadow-inner">
              {chatMessages.length === 0 && (
                <div className="h-full flex items-center justify-center text-gray-400 text-sm">
                  The room is quiet. Say something!
                </div>
              )}
              {chatMessages.map((msg) => {
                const isAI = msg.sender_type === 'ai';
                return (
                  <div key={msg.id} className="flex gap-3 text-sm animate-fade-in items-start transition-all">
                    <Avatar 
                      size="small" 
                      shape="square" 
                      className={`rounded shrink-0 mt-0.5 ${isAI ? 'bg-purple-500' : 'bg-indigo-100 text-indigo-700'}`}
                      icon={isAI ? <RobotOutlined /> : undefined}
                    >
                      {!isAI && msg.sender_name?.charAt(0).toUpperCase()}
                    </Avatar>
                    <div className="flex-1">
                      <Text strong className={isAI ? "text-purple-600" : "text-gray-800"}>
                        {isAI ? 'AI' : msg.sender_name}
                      </Text>
                      <Text className="ml-2 text-gray-600 block sm:inline">{msg.content}</Text>
                    </div>
                  </div>
                );
              })}
              <div ref={bottomRef} />
            </div>
          </div>

          {/* Controls Footer */}
          <div className="p-4 border-t border-gray-100 bg-white flex justify-center w-full">
            {role === 'speaker' && (
              <Tooltip title={isConnecting ? 'Connecting…' : isRecording ? 'Release to Send' : 'Hold to Talk'}>
                <Button
                  type="primary"
                  shape="circle"
                  size="large"
                  icon={isRecording ? <AudioOutlined /> : <AudioMutedOutlined />}
                  loading={isConnecting}
                  onMouseDown={handleMouseDown}
                  onMouseUp={handleMouseUp}
                  onMouseLeave={handleMouseUp}
                  onTouchStart={handleMouseDown}
                  onTouchEnd={handleMouseUp}
                  className={`w-16 h-16 text-2xl shadow-lg transition-all ${
                    isRecording 
                      ? 'bg-red-500 hover:bg-red-600 scale-110 shadow-red-500/50 ring-4 ring-red-100' 
                      : 'bg-indigo-600 hover:bg-indigo-700 hover:scale-105'
                  }`}
                />
              </Tooltip>
            )}

            {role === 'listener' && (
              <div className="flex justify-center w-full">
                <Button 
                  size="large" 
                  icon={<SoundOutlined />} 
                  onClick={raiseHand}
                  className="bg-yellow-50 border-yellow-300 text-yellow-700 hover:bg-yellow-100 hover:border-yellow-400 hover:text-yellow-800 rounded-full font-medium px-8 shadow-sm"
                >
                  Raise Hand to Speak
                </Button>
              </div>
            )}
          </div>
        </Content>

        {/* Listeners Sidebar */}
        <Sider width={280} theme="light" className="hidden lg:block bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50">
            <Text strong className="text-gray-700 flex items-center gap-2">
              <TeamOutlined /> Listeners ({listeners.length})
            </Text>
          </div>
          <List
            className="overflow-y-auto h-[calc(100%-55px)]"
            itemLayout="horizontal"
            dataSource={listeners}
            locale={{ emptyText: <span className="text-gray-400 text-sm">No listeners</span> }}
            renderItem={(l) => (
              <List.Item className="px-5 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors">
                <List.Item.Meta
                  avatar={<Avatar size="small" className="bg-gray-200 text-gray-500"><UserOutlined /></Avatar>}
                  title={<Text className="text-sm font-medium">{l.user_id.slice(0, 8)}</Text>}
                />
                <div className="flex items-center gap-2">
                  {l.hand_raised && <Tooltip title="Hand Raised"><SoundOutlined className="text-yellow-500" /></Tooltip>}
                  {role === 'speaker' && l.hand_raised && (
                    <Button type="link" size="small" onClick={() => promote(l.user_id)} className="p-0 h-auto text-xs font-semibold text-indigo-600">
                      Promote
                    </Button>
                  )}
                </div>
              </List.Item>
            )}
          />
        </Sider>
      </Layout>
    </Layout>
  );
}

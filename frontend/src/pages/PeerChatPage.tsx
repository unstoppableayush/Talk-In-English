import { useEffect, useRef, useState } from 'react';
import { Button, Typography, Avatar, Layout, Space, Tag, Tooltip, Segmented } from 'antd';
import { TeamOutlined, UserOutlined, RobotOutlined, AudioOutlined, AudioMutedOutlined } from '@ant-design/icons';
import api from '@/lib/api';
import { useRoomStore } from '@/stores/roomStore';
import { useAudioSocket, type SttMode } from '@/hooks/useAudioSocket';
import { useSessionSocket } from '@/hooks/useSessionSocket';

const { Title, Text } = Typography;
const { Content } = Layout;

export default function PeerChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [sttMode, setSttMode] = useState<SttMode>('browser');
  const store = useRoomStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  const { sendMessage } = useSessionSocket(sessionId, 'speaker');
  const { startRecording, stopRecording, isRecording, isConnecting } = useAudioSocket(sessionId, {
    mode: sttMode,
    onResult: (text) => {
      if (text) sendMessage(text);
    },
  });

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

  const handleMouseDown = () => startRecording();
  const handleMouseUp = () => stopRecording();

  if (!sessionId) {
    return (
      <div className="flex flex-col items-center justify-center py-24 px-4 text-center">
        <TeamOutlined className="text-6xl text-indigo-500 mb-6" />
        <Title level={2}>Peer Chat</Title>
        <Text type="secondary" className="mb-8 max-w-md text-lg">
          Practice 1-on-1 with another speaker. AI monitors silently and gives feedback after to help you improve.
        </Text>
        <Button
          type="primary"
          size="large"
          loading={starting}
          onClick={startSession}
          className="bg-indigo-600 px-8 h-12 text-lg rounded-full shadow-lg hover:shadow-xl transition-all"
        >
          {starting ? 'Creating Room...' : 'Start Peer Session'}
        </Button>
      </div>
    );
  }

  return (
    <Content className="flex flex-col h-[calc(100vh-10rem)] max-w-4xl mx-auto w-full bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Avatar icon={<TeamOutlined />} className="bg-indigo-600" />
          <div>
            <Title level={5} className="!mb-0">Peer Practice Room</Title>
            <Space className="text-xs text-gray-500 mt-1">
              <span>{store.speakerCount} speaker(s)</span>
              <Tag color="green" icon={<RobotOutlined />}>AI monitoring</Tag>
            </Space>
          </div>
        </div>
        <Segmented
          size="small"
          value={sttMode}
          onChange={(v) => setSttMode(v as SttMode)}
          options={[
            { label: 'Browser STT', value: 'browser' },
            { label: 'Deepgram STT', value: 'deepgram' },
          ]}
        />
      </div>

      <div className="flex-1 p-6 overflow-y-auto space-y-6 bg-gray-50/50">
        {store.messages.length === 0 && (
          <div className="flex justify-center items-center h-full text-center text-gray-400 flex-col">
             <TeamOutlined className="text-4xl mb-4 text-gray-300" />
             <p>Waiting for the other peer to join...</p>
          </div>
        )}
        {store.messages.map((msg) => {
          const isUser = msg.sender_type === 'user';
          
          return (
            <div
              key={msg.id}
              className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`flex gap-3 max-w-[80%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
                <Avatar 
                  icon={<UserOutlined />} 
                  className={isUser ? "bg-blue-500 shrink-0" : "bg-purple-500 shrink-0"} 
                >
                  {msg.sender_name?.charAt(0).toUpperCase()}
                </Avatar>
                <div
                  className={`rounded-2xl px-5 py-3 shadow-sm flex flex-col ${
                    isUser
                      ? 'bg-indigo-600 text-white rounded-tr-sm items-end'
                      : 'bg-white text-gray-800 border border-gray-100 rounded-tl-sm items-start'
                  }`}
                >
                  {!isUser && msg.sender_name && (
                    <Text className="text-xs text-gray-400 mb-1 leading-none">{msg.sender_name}</Text>
                  )}
                  {isUser && msg.sender_name && (
                    <Text className="text-xs text-indigo-200 mb-1 leading-none">{msg.sender_name}</Text>
                  )}
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                </div>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      <div className="p-8 bg-white border-t border-gray-100 flex justify-center items-center">
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
            className={`w-20 h-20 text-3xl shadow-lg transition-all ${
              isRecording 
                ? 'bg-red-500 hover:bg-red-600 scale-110 shadow-red-500/50 ring-4 ring-red-100' 
                : 'bg-indigo-600 hover:bg-indigo-700 hover:scale-105'
            }`}
          />
        </Tooltip>
      </div>
    </Content>
  );
}

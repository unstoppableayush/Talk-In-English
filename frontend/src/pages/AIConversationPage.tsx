import { useEffect, useRef, useState } from 'react';
import { Button, Typography, Avatar, Layout, Tooltip, Input, Segmented, message } from 'antd';
import { RobotOutlined, UserOutlined, AudioOutlined, AudioMutedOutlined, SendOutlined } from '@ant-design/icons';
import api from '@/lib/api';
import { useRoomStore } from '@/stores/roomStore';
import { useAudioSocket, type SttMode } from '@/hooks/useAudioSocket';
import { useSessionSocket } from '@/hooks/useSessionSocket';

const { Title, Text } = Typography;
const { Content } = Layout;

export default function AIConversationPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [textInput, setTextInput] = useState('');
  const [sttMode, setSttMode] = useState<SttMode>('browser');
  const store = useRoomStore();
  const bottomRef = useRef<HTMLDivElement>(null);
  
  // Track last spoken message ID to prevent re-speaking on remounts
  const [lastSpokenId, setLastSpokenId] = useState<string | null>(null);

  const { sendMessage } = useSessionSocket(sessionId, 'speaker');
  const { startRecording, stopRecording, isRecording, isConnecting, requestTTS } = useAudioSocket(sessionId, {
    mode: sttMode,
    onResult: (text) => {
      if (text) sendMessage(text);
    },
  });

  // Auto-scroll and TTS trigger
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    
    // Check for new AI messages to speak
    const msgs = store.messages;
    if (msgs.length > 0) {
      const lastMsg = msgs[msgs.length - 1];
      if (lastMsg.sender_type === 'ai' && lastMsg.id !== lastSpokenId) {
        requestTTS(lastMsg.content);
        setLastSpokenId(lastMsg.id);
      }
    }
  }, [store.messages, lastSpokenId, requestTTS]);

  // Cleanup on unmount
  useEffect(() => {
    return () => store.reset();
  }, []);

  const startSession = async () => {
    setStarting(true);
    try {
      const { data: room } = await api.post('/rooms', {
        name: 'AI Practice',
        room_type: 'one_on_one',
        topic: 'General conversation',
      });
      const { data: session } = await api.post(`/rooms/${room.id}/join`, { role: 'speaker' });
      setSessionId(session.session_id);
    } catch (err) {
      message.error('Failed to start session. Please try again.');
    } finally {
      setStarting(false);
    }
  };

  const handleMouseDown = () => startRecording();
  const handleMouseUp = () => stopRecording();

  const handleSendText = () => {
    const msg = textInput.trim();
    if (!msg) return;
    sendMessage(msg);
    setTextInput('');
  };

  if (!sessionId) {
    return (
      <div className="flex flex-col items-center justify-center py-24 px-4 text-center">
        <RobotOutlined className="text-6xl text-indigo-500 mb-6" />
        <Title level={2}>AI Conversation</Title>
        <Text type="secondary" className="mb-8 max-w-md text-lg">
          Practice speaking with a state-of-the-art AI partner to improve your fluency and confidence.
        </Text>
        <Button
          type="primary"
          size="large"
          loading={starting}
          onClick={startSession}
          className="bg-indigo-600 px-8 h-12 text-lg rounded-full shadow-lg hover:shadow-xl transition-all"
        >
          {starting ? 'Starting Session...' : 'Start Conversation'}
        </Button>
      </div>
    );
  }

  return (
    <Content className="flex flex-col h-[calc(100vh-10rem)] max-w-4xl mx-auto w-full bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Avatar icon={<RobotOutlined />} className="bg-indigo-600" />
          <div>
            <Title level={5} className="!mb-0">AI Partner</Title>
            <Text type="secondary" className="text-xs">
              Powered by Multi-Provider LLM
            </Text>
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

      {/* Messages */}
      <div className="flex-1 p-6 overflow-y-auto space-y-6 bg-gray-50/50">
        {store.messages.length === 0 && (
          <div className="flex justify-center items-center h-full text-center text-gray-400 flex-col">
             <RobotOutlined className="text-4xl mb-4 text-gray-300" />
             <p>Start the conversation by sending a message.</p>
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
                  icon={isUser ? <UserOutlined /> : <RobotOutlined />} 
                  className={isUser ? "bg-blue-500 shrink-0" : "bg-indigo-600 shrink-0"} 
                />
                <div
                  className={`rounded-2xl px-5 py-3 shadow-sm ${
                    isUser
                      ? 'bg-indigo-600 text-white rounded-tr-sm'
                      : 'bg-white text-gray-800 border border-gray-100 rounded-tl-sm'
                  }`}
                >
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                </div>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Input Area */}
      <div className="px-4 py-3 bg-white border-t border-gray-100 flex items-center gap-3">
        <Input
          placeholder="Type a message..."
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          onPressEnter={handleSendText}
          className="flex-1 rounded-full"
          size="large"
        />
        <Button
          type="primary"
          shape="circle"
          size="large"
          icon={<SendOutlined />}
          onClick={handleSendText}
          disabled={!textInput.trim()}
          className="bg-indigo-600 hover:bg-indigo-700"
        />
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
            className={`transition-all ${
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

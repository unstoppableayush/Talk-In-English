import { useCallback, useEffect, useRef } from 'react';
import { buildWSUrl } from '@/lib/ws';
import { useRoomStore } from '@/stores/roomStore';
import type { WSEvent, ChatMessage } from '@/types';

export function useSessionSocket(sessionId: string | null, role: 'speaker' | 'listener' = 'speaker') {
  const wsRef = useRef<WebSocket | null>(null);
  const store = useRoomStore();

  useEffect(() => {
    if (!sessionId) return;

    const url = buildWSUrl(`/session/${sessionId}?role=${role}`);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => store.setConnected(true);

    ws.onmessage = (evt) => {
      const msg: WSEvent = JSON.parse(evt.data);

      switch (msg.event) {
        case 'connection.accepted':
          store.setSession(
            (msg.data as { session_id: string }).session_id,
            (msg.data as { mode: string }).mode,
            (msg.data as { role: 'speaker' | 'listener' }).role,
          );
          break;

        case 'session.state':
          store.setCounts(
            (msg.data as { speaker_count: number }).speaker_count,
            (msg.data as { listener_count: number }).listener_count,
          );
          break;

        case 'message.received':
          store.addMessage(msg.data as ChatMessage);
          break;

        case 'participant.joined':
        case 'participant.left':
        case 'participant.promoted':
          store.setCounts(
            (msg.data as { speaker_count: number }).speaker_count,
            (msg.data as { listener_count: number }).listener_count,
          );
          break;

        case 'moderation.action':
          store.addMessage({
            id: (msg.data as { id: string }).id,
            sender_id: 'ai',
            sender_name: 'AI Moderator',
            sender_type: 'ai',
            content: (msg.data as { message: string }).message,
            message_type: 'moderation',
            created_at: (msg.data as { created_at: string }).created_at,
          });
          break;
      }
    };

    ws.onclose = () => store.setConnected(false);

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [sessionId, role]);

  const sendMessage = useCallback(
    (content: string) => {
      wsRef.current?.send(
        JSON.stringify({ event: 'message.send', data: { content } }),
      );
    },
    [],
  );

  const raiseHand = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ event: 'hand.raise', data: {} }));
  }, []);

  const promote = useCallback((userId: string) => {
    wsRef.current?.send(
      JSON.stringify({ event: 'participant.promote', data: { user_id: userId } }),
    );
  }, []);

  return { sendMessage, raiseHand, promote, ws: wsRef };
}

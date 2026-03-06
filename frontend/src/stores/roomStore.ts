import { create } from 'zustand';
import type { ChatMessage, Participant } from '@/types';

interface RoomState {
  sessionId: string | null;
  mode: string | null;
  role: 'speaker' | 'listener' | null;
  messages: ChatMessage[];
  participants: Participant[];
  speakerCount: number;
  listenerCount: number;
  connected: boolean;

  setSession: (sessionId: string, mode: string, role: 'speaker' | 'listener') => void;
  addMessage: (msg: ChatMessage) => void;
  setParticipants: (p: Participant[]) => void;
  setCounts: (speakers: number, listeners: number) => void;
  setConnected: (c: boolean) => void;
  reset: () => void;
}

export const useRoomStore = create<RoomState>((set) => ({
  sessionId: null,
  mode: null,
  role: null,
  messages: [],
  participants: [],
  speakerCount: 0,
  listenerCount: 0,
  connected: false,

  setSession: (sessionId, mode, role) => set({ sessionId, mode, role }),
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  setParticipants: (participants) => set({ participants }),
  setCounts: (speakerCount, listenerCount) => set({ speakerCount, listenerCount }),
  setConnected: (connected) => set({ connected }),
  reset: () =>
    set({
      sessionId: null,
      mode: null,
      role: null,
      messages: [],
      participants: [],
      speakerCount: 0,
      listenerCount: 0,
      connected: false,
    }),
}));

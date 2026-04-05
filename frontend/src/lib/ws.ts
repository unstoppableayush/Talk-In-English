import { useAuthStore } from '@/stores/authStore';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || '';

/**
 * Build an authenticated WebSocket URL.
 */
export function buildWSUrl(path: string): string {
  const token = useAuthStore.getState().accessToken;
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = WS_BASE_URL || window.location.host;
  const separator = path.includes('?') ? '&' : '?';
  return `${protocol}//${host}/ws${path}${separator}token=${token}`;
}

import { useAuthStore } from '@/stores/authStore';

/**
 * Build an authenticated WebSocket URL.
 */
export function buildWSUrl(path: string): string {
  const token = useAuthStore.getState().accessToken;
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const separator = path.includes('?') ? '&' : '?';
  return `${protocol}//${host}/ws${path}${separator}token=${token}`;
}

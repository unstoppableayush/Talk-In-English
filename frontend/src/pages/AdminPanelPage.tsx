import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { Room } from '@/types';
import { Trash2, Users, Shield, RefreshCw } from 'lucide-react';

interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  role: string;
  xp: number;
  is_active: boolean;
  created_at: string;
}

export default function AdminPanelPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<'rooms' | 'users'>('rooms');

  // Rooms
  const { data: rooms = [] } = useQuery<Room[]>({
    queryKey: ['admin-rooms'],
    queryFn: () => api.get('/rooms').then((r) => r.data),
  });

  const deleteRoom = useMutation({
    mutationFn: (id: string) => api.delete(`/rooms/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-rooms'] }),
  });

  // Users — uses a hypothetical admin endpoint; adjust URL as needed
  const { data: users = [] } = useQuery<AdminUser[]>({
    queryKey: ['admin-users'],
    queryFn: () => api.get('/auth/users').then((r) => r.data),
    enabled: tab === 'users',
  });

  const tabClass = (t: string) =>
    `px-4 py-2 text-sm font-medium rounded-lg ${
      tab === t ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
    }`;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Admin Panel</h1>
        <button
          onClick={() => qc.invalidateQueries({ queryKey: [`admin-${tab}`] })}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        <button className={tabClass('rooms')} onClick={() => setTab('rooms')}>
          <span className="flex items-center gap-1">
            <Users className="h-4 w-4" /> Rooms ({rooms.length})
          </span>
        </button>
        <button className={tabClass('users')} onClick={() => setTab('users')}>
          <span className="flex items-center gap-1">
            <Shield className="h-4 w-4" /> Users
          </span>
        </button>
      </div>

      {/* Rooms table */}
      {tab === 'rooms' && (
        <div className="overflow-hidden rounded-xl bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-gray-50">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Language</th>
                <th className="px-4 py-3 font-medium">Speakers</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rooms.map((room) => (
                <tr key={room.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{room.name}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-600">
                      {room.room_type}
                    </span>
                  </td>
                  <td className="px-4 py-3">{room.language}</td>
                  <td className="px-4 py-3">
                    {room.speaker_count}/{room.max_speakers}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        room.is_active
                          ? 'bg-green-50 text-green-600'
                          : 'bg-gray-100 text-gray-500'
                      }`}
                    >
                      {room.is_active ? 'Active' : 'Closed'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => deleteRoom.mutate(room.id)}
                      disabled={deleteRoom.isPending}
                      className="rounded p-1 text-red-500 hover:bg-red-50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {rooms.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                    No rooms found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Users table */}
      {tab === 'users' && (
        <div className="overflow-hidden rounded-xl bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-gray-50">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">XP</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Joined</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{u.display_name}</td>
                  <td className="px-4 py-3">{u.email}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        u.role === 'admin'
                          ? 'bg-red-50 text-red-600'
                          : u.role === 'moderator'
                            ? 'bg-yellow-50 text-yellow-600'
                            : 'bg-gray-100 text-gray-500'
                      }`}
                    >
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3">{u.xp.toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`h-2 w-2 inline-block rounded-full ${
                        u.is_active ? 'bg-green-500' : 'bg-gray-300'
                      }`}
                    />
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                    No users found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Table, Tabs, Button, Tag, Typography, Space, Popconfirm } from 'antd';
import { 
  TeamOutlined, 
  SafetyCertificateOutlined, 
  ReloadOutlined, 
  DeleteOutlined 
} from '@ant-design/icons';
import api from '@/lib/api';
import type { Room } from '@/types';

const { Title } = Typography;

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
  const [activeTab, setActiveTab] = useState('rooms');

  // Rooms
  const { data: rooms = [], isLoading: roomsLoading } = useQuery<Room[]>({
    queryKey: ['admin-rooms'],
    queryFn: () => api.get('/rooms').then((r) => r.data),
  });

  const deleteRoom = useMutation({
    mutationFn: (id: string) => api.delete(`/rooms/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-rooms'] }),
  });

  // Users
  const { data: users = [], isLoading: usersLoading } = useQuery<AdminUser[]>({
    queryKey: ['admin-users'],
    queryFn: () => api.get('/auth/users').then((r) => r.data),
    enabled: activeTab === 'users',
  });

  const handleRefresh = () => {
    qc.invalidateQueries({ queryKey: [`admin-${activeTab}`] });
  };

  const roomColumns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <span className="font-medium">{text}</span>,
    },
    {
      title: 'Type',
      dataIndex: 'room_type',
      key: 'room_type',
      render: (type: string) => (
        <Tag color="geekblue" className="rounded-full">{type}</Tag>
      ),
    },
    {
      title: 'Language',
      dataIndex: 'language',
      key: 'language',
    },
    {
      title: 'Speakers',
      key: 'speakers',
      render: (_: unknown, record: Room) => (
        `${record.speaker_count}/${record.max_speakers}`
      ),
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'status',
      render: (isActive: boolean) => (
        <Tag color={isActive ? 'success' : 'default'} className="rounded-full">
          {isActive ? 'Active' : 'Closed'}
        </Tag>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: Room) => (
        <Popconfirm
          title="Delete room"
          description="Are you sure you want to delete this room?"
          onConfirm={() => deleteRoom.mutate(record.id)}
          okText="Yes"
          cancelText="No"
          okButtonProps={{ danger: true }}
        >
          <Button 
            type="text" 
            danger 
            icon={<DeleteOutlined />} 
            loading={deleteRoom.isPending}
          />
        </Popconfirm>
      ),
    },
  ];

  const userColumns = [
    {
      title: 'Name',
      dataIndex: 'display_name',
      key: 'name',
      render: (text: string) => <span className="font-medium">{text}</span>,
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
      render: (role: string) => {
        let color = 'default';
        if (role === 'admin') color = 'volcano';
        if (role === 'moderator') color = 'gold';
        return <Tag color={color} className="uppercase text-[10px] tracking-wider">{role}</Tag>;
      },
    },
    {
      title: 'XP',
      dataIndex: 'xp',
      key: 'xp',
      render: (xp: number) => xp.toLocaleString(),
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'status',
      render: (isActive: boolean) => (
        <Space>
          <div className={`w-2 h-2 rounded-full ${isActive ? 'bg-green-500' : 'bg-gray-300'}`} />
          {isActive ? 'Active' : 'Inactive'}
        </Space>
      ),
    },
    {
      title: 'Joined',
      dataIndex: 'created_at',
      key: 'joined',
      render: (dateStr: string) => new Date(dateStr).toLocaleDateString(),
    },
  ];

  const items = [
    {
      key: 'rooms',
      label: <span className="flex items-center gap-2"><TeamOutlined /> Rooms</span>,
      children: (
        <Table 
          columns={roomColumns} 
          dataSource={rooms} 
          rowKey="id" 
          loading={roomsLoading}
          pagination={{ pageSize: 10 }}
          className="bg-white rounded-xl overflow-hidden shadow-sm border border-gray-100"
        />
      ),
    },
    {
      key: 'users',
      label: <span className="flex items-center gap-2"><SafetyCertificateOutlined /> Users</span>,
      children: (
        <Table 
          columns={userColumns} 
          dataSource={users} 
          rowKey="id" 
          loading={usersLoading}
          pagination={{ pageSize: 10 }}
          className="bg-white rounded-xl overflow-hidden shadow-sm border border-gray-100"
        />
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <Title level={3} className="!mb-0">Admin Panel</Title>
        <Button 
          type="default" 
          icon={<ReloadOutlined />} 
          onClick={handleRefresh}
        >
          Refresh
        </Button>
      </div>

      <Tabs 
        activeKey={activeTab} 
        onChange={setActiveTab} 
        items={items} 
        type="card"
        className="admin-tabs"
      />
    </div>
  );
}

import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import {
  LayoutDashboard,
  MessageSquare,
  Users,
  Mic,
  LogOut,
  Shield,
  Theater,
} from 'lucide-react';
import { Layout, Menu, Typography, Dropdown, Avatar, Space } from 'antd';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

export default function AppLayout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/auth/login');
  };

  const menuItems = [
    { key: '/', icon: <LayoutDashboard className="w-4 h-4" />, label: 'Dashboard' },
    { key: '/ai-chat', icon: <MessageSquare className="w-4 h-4" />, label: 'AI Chat' },
    { key: '/peer-chat', icon: <Users className="w-4 h-4" />, label: 'Peer Chat' },
    { key: '/roleplay', icon: <Theater className="w-4 h-4" />, label: 'Role Play' },
    { key: '/admin', icon: <Shield className="w-4 h-4" />, label: 'Admin' },
  ];

  const userMenuItems = [
    {
      key: '1',
      label: (
        <div className="flex flex-col">
          <Text strong>{user?.display_name}</Text>
          <Text type="secondary" className="text-xs">{user?.email}</Text>
        </div>
      ),
    },
    { type: 'divider' as const },
    {
      key: '2',
      icon: <LogOut className="w-4 h-4" />,
      label: 'Sign out',
      onClick: handleLogout,
      danger: true,
    },
  ];

  return (
    <Layout className="min-h-screen">
      <Sider width={256} theme="dark" breakpoint="lg" collapsedWidth="0">
        <div className="flex items-center gap-2 px-6 py-5 text-white">
          <Mic className="h-6 w-6 text-indigo-400" />
          <span className="text-lg font-bold">Speaking App</span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header className="flex justify-end items-center px-6 bg-white shadow-sm">
          <Dropdown menu={{ items: userMenuItems }} trigger={['click']} placement="bottomRight">
            <Space className="cursor-pointer">
              <Avatar className="bg-indigo-500">{user?.display_name?.charAt(0).toUpperCase()}</Avatar>
              <Text strong className="hidden sm:block">{user?.display_name}</Text>
            </Space>
          </Dropdown>
        </Header>
        <Content className="m-6 overflow-y-auto">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

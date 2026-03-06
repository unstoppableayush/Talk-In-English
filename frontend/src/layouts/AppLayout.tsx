import { Outlet, NavLink, useNavigate } from 'react-router-dom';
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

const links = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/ai-chat', label: 'AI Chat', icon: MessageSquare },
  { to: '/peer-chat', label: 'Peer Chat', icon: Users },
  { to: '/roleplay', label: 'Role Play', icon: Theater },
  { to: '/admin', label: 'Admin', icon: Shield },
];

export default function AppLayout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/auth/login');
  };

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="flex w-64 flex-col bg-primary-900 text-white">
        <div className="flex items-center gap-2 px-6 py-5">
          <Mic className="h-6 w-6 text-primary-300" />
          <span className="text-lg font-bold">Speaking App</span>
        </div>

        <nav className="flex-1 space-y-1 px-3">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                  isActive
                    ? 'bg-primary-700 text-white'
                    : 'text-primary-300 hover:bg-primary-800 hover:text-white'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-primary-800 px-4 py-4">
          <div className="mb-2 text-sm font-medium">{user?.display_name}</div>
          <div className="mb-3 text-xs text-primary-400">{user?.email}</div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-primary-400 hover:text-white"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-gray-50 p-6">
        <Outlet />
      </main>
    </div>
  );
}

import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import AuthLayout from '@/layouts/AuthLayout';
import AppLayout from '@/layouts/AppLayout';
import LoginPage from '@/pages/auth/LoginPage';
import RegisterPage from '@/pages/auth/RegisterPage';
import DashboardPage from '@/pages/DashboardPage';
import AIConversationPage from '@/pages/AIConversationPage';
import PeerChatPage from '@/pages/PeerChatPage';
import PublicRoomPage from '@/pages/PublicRoomPage';
import ScoreReportPage from '@/pages/ScoreReportPage';
import AdminPanelPage from '@/pages/AdminPanelPage';
import RolePlayPage from '@/pages/RolePlayPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.accessToken);
  if (!token) return <Navigate to="/auth/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      {/* Public auth routes */}
      <Route element={<AuthLayout />}>
        <Route path="/auth/login" element={<LoginPage />} />
        <Route path="/auth/register" element={<RegisterPage />} />
      </Route>

      {/* Protected app routes */}
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/ai-chat" element={<AIConversationPage />} />
        <Route path="/peer-chat" element={<PeerChatPage />} />
        <Route path="/room/:roomId" element={<PublicRoomPage />} />
        <Route path="/scores/:sessionId" element={<ScoreReportPage />} />
        <Route path="/admin" element={<AdminPanelPage />} />
        <Route path="/roleplay" element={<RolePlayPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

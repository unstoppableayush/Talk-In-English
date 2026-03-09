import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Form, Input, Button, Divider, Alert } from 'antd';
import { UserOutlined, MailOutlined, LockOutlined } from '@ant-design/icons';
import api from '@/lib/api';
import { useAuthStore } from '@/stores/authStore';
import type { AuthResponse } from '@/types';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: Record<string, unknown>) => void;
          renderButton: (el: HTMLElement, config: Record<string, unknown>) => void;
        };
      };
    };
  }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

export default function RegisterPage() {
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const setAuth = useAuthStore((s) => s.setAuth);
  const navigate = useNavigate();
  const googleBtnRef = useRef<HTMLDivElement>(null);

  const handleGoogleResponse = useCallback(
    async (response: { credential: string }) => {
      setError('');
      setLoading(true);
      try {
        const { data } = await api.post<AuthResponse>('/auth/google', {
          credential: response.credential,
        });
        setAuth(data.user, data.tokens.access_token, data.tokens.refresh_token);
        navigate('/');
      } catch (err: unknown) {
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setError(msg || 'Google sign-up failed');
      } finally {
        setLoading(false);
      }
    },
    [setAuth, navigate],
  );

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !window.google || !googleBtnRef.current) return;
    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: handleGoogleResponse,
    });
    window.google.accounts.id.renderButton(googleBtnRef.current, {
      theme: 'outline',
      size: 'large',
      width: '100%',
      text: 'signup_with',
    });
  }, [handleGoogleResponse]);

  const onFinish = async (values: any) => {
    setError('');
    setLoading(true);
    try {
      const { data } = await api.post<AuthResponse>('/auth/register', {
        email: values.email,
        display_name: values.display_name,
        password: values.password,
      });
      setAuth(data.user, data.tokens.access_token, data.tokens.refresh_token);
      navigate('/');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-gray-800 text-center mb-6">Create Account</h2>

      {error && <Alert message={error} type="error" showIcon className="mb-4" />}

      <Form
        name="register_form"
        layout="vertical"
        onFinish={onFinish}
        size="large"
      >
        <Form.Item
          name="display_name"
          rules={[{ required: true, message: 'Please input your Display Name!' }]}
        >
          <Input prefix={<UserOutlined className="text-gray-400" />} placeholder="Display Name" />
        </Form.Item>

        <Form.Item
          name="email"
          rules={[{ required: true, message: 'Please input your Email!' }, { type: 'email', message: 'The input is not valid E-mail!' }]}
        >
          <Input prefix={<MailOutlined className="text-gray-400" />} placeholder="Email" />
        </Form.Item>

        <Form.Item
          name="password"
          rules={[
            { required: true, message: 'Please input your Password!' },
            { min: 8, message: 'Password must be at least 8 characters' }
          ]}
        >
          <Input.Password prefix={<LockOutlined className="text-gray-400" />} placeholder="Password (8+ chars)" />
        </Form.Item>

        <Form.Item>
          <Button type="primary" htmlType="submit" className="w-full bg-indigo-600" loading={loading}>
            Register
          </Button>
        </Form.Item>
      </Form>

      {GOOGLE_CLIENT_ID && (
        <>
          <Divider plain className="text-gray-400 text-xs">OR</Divider>
          <div ref={googleBtnRef} className="flex justify-center mb-4" />
        </>
      )}

      <p className="text-center text-sm text-gray-500">
        Already have an account?{' '}
        <Link to="/auth/login" className="text-indigo-600 hover:text-indigo-800 font-medium">
          Sign In
        </Link>
      </p>
    </div>
  );
}

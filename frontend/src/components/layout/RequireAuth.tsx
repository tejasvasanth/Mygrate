import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { Skeleton } from 'antd';
import { useAuth } from '@/hooks/useAuth';

/**
 * Gates the app routes behind Supabase auth. When Supabase isn't configured
 * (pure local dev) it passes through, matching the backend's dev fallback.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading, configured } = useAuth();

  if (!configured) return <>{children}</>;
  if (loading) {
    return (
      <div style={{ padding: 48, maxWidth: 720, margin: '0 auto' }}>
        <Skeleton active paragraph={{ rows: 6 }} />
      </div>
    );
  }
  if (!user) return <Navigate to="/" replace />;
  return <>{children}</>;
}

import { Card, Descriptions, Space, Tag, Typography } from 'antd';
import { ComplianceMatrix } from '@/components/migration/ComplianceMatrix';
import { useAuth } from '@/hooks/useAuth';
import { isSupabaseConfigured } from '@/lib/supabase';

const { Text, Title } = Typography;

export function Settings() {
  const { user, configured } = useAuth();

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <div>
        <Title level={3} style={{ margin: 0, letterSpacing: '-0.02em' }}>
          Settings
        </Title>
        <Text type="secondary" style={{ fontSize: 13.5 }}>
          Session and environment.
        </Text>
      </div>

      <Card variant="outlined" className="glass-panel" style={{ borderRadius: 14 }}>
        <Descriptions
          column={1}
          labelStyle={{ width: 220 }}
          items={[
            {
              key: 'account',
              label: 'Account',
              children: <Text>{user?.email ?? 'Local session (no auth)'}</Text>,
            },
            {
              key: 'supabase',
              label: 'Supabase',
              children: configured ? (
                <Tag color="success">Configured</Tag>
              ) : (
                <Tag>Not configured</Tag>
              ),
            },
            {
              key: 'api',
              label: 'API base URL',
              children: (
                <Text code>
                  {(import.meta.env.VITE_API_BASE_URL as string | undefined) ??
                    'http://localhost:8000'}
                </Text>
              ),
            },
            {
              key: 'realtime',
              label: 'Live updates',
              children: isSupabaseConfigured ? (
                <Tag color="success">Supabase Realtime</Tag>
              ) : (
                <Tag>Unavailable without Supabase</Tag>
              ),
            },
          ]}
        />
      </Card>

      <ComplianceMatrix />
    </Space>
  );
}

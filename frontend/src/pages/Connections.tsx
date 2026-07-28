import { useState } from 'react';
import {
  App as AntApp,
  Button,
  Card,
  Empty,
  Popconfirm,
  Space,
  Table,
  Typography,
} from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { DbChip } from '@/components/migration/DbBadge';
import { SaveConnectionModal } from '@/components/migration/SaveConnectionModal';
import { useDeleteConnection, useSavedConnections } from '@/hooks/useMigration';
import { apiErrorMessage } from '@/lib/api';
import { timeAgo } from '@/lib/utils';
import type { DbType, SavedConnection } from '@/types';

const { Text, Title } = Typography;

export function Connections() {
  const { message } = AntApp.useApp();
  const { data: connections, isLoading } = useSavedConnections();
  const deleteConnection = useDeleteConnection();
  const [saveOpen, setSaveOpen] = useState(false);

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }} align="start">
        <div>
          <Title level={3} style={{ margin: 0, letterSpacing: '-0.02em' }}>
            Saved connections
          </Title>
          <Text type="secondary" style={{ fontSize: 13.5 }}>
            Credentials live in Supabase Vault — only nicknames and hosts are stored here.
          </Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setSaveOpen(true)}>
          Save connection
        </Button>
      </Space>

      <SaveConnectionModal open={saveOpen} onClose={() => setSaveOpen(false)} />

      <Card variant="outlined" className="glass-panel" style={{ borderRadius: 14 }} styles={{ body: { padding: 0 } }}>
        <Table<SavedConnection>
          rowKey="id"
          loading={isLoading}
          dataSource={connections ?? []}
          pagination={false}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <Space direction="vertical" size={8} style={{ padding: '16px 0' }}>
                    <Text>No saved connections yet.</Text>
                    <Text type="secondary" style={{ fontSize: 12.5 }}>
                      Save one to reuse it across migrations without pasting the
                      credential each time.
                    </Text>
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={() => setSaveOpen(true)}
                    >
                      Save your first connection
                    </Button>
                  </Space>
                }
              />
            ),
          }}
          columns={[
            {
              title: 'Nickname',
              dataIndex: 'nickname',
              render: (v: string) => <Text strong>{v}</Text>,
            },
            {
              title: 'Engine',
              dataIndex: 'db_type',
              render: (v: DbType) => <DbChip type={v} size="small" />,
            },
            {
              title: 'Host',
              dataIndex: 'host',
              render: (v: string | null, row) =>
                v ? (
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    {v}
                    {row.port ? `:${row.port}` : ''}
                  </Text>
                ) : (
                  <Text type="secondary">—</Text>
                ),
            },
            {
              title: 'Database',
              dataIndex: 'database_name',
              render: (v: string | null) => <Text type="secondary">{v ?? '—'}</Text>,
            },
            {
              title: 'Added',
              dataIndex: 'created_at',
              render: (v: string) => (
                <Text type="secondary" style={{ fontSize: 12.5 }}>
                  {timeAgo(v)}
                </Text>
              ),
            },
            {
              title: '',
              key: 'actions',
              width: 60,
              render: (_: unknown, row) => (
                <Popconfirm
                  title="Delete this connection?"
                  description="The credential is removed from Vault as well."
                  okButtonProps={{ danger: true }}
                  onConfirm={() =>
                    deleteConnection.mutate(row.id, {
                      onSuccess: () => message.success('Connection deleted.'),
                      onError: (e) => message.error(apiErrorMessage(e)),
                    })
                  }
                >
                  <Button type="text" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  );
}

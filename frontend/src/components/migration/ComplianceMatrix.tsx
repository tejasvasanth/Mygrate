import { Card, Skeleton, Space, Table, Tag, Typography } from 'antd';
import { CheckCircleFilled, CloseCircleFilled, DatabaseOutlined } from '@ant-design/icons';
import { useCompliance } from '@/hooks/useMigration';
import { brand } from '@/theme';
import type { ComplianceEntry } from '@/types';

const { Text } = Typography;

function SupportTag({ ok }: { ok: boolean }) {
  return ok ? (
    <Tag color="green" icon={<CheckCircleFilled />}>
      supported
    </Tag>
  ) : (
    <Tag color="red" icon={<CloseCircleFilled />}>
      unavailable
    </Tag>
  );
}

/** Live capability matrix: which DB types this deployment can actually use. */
export function ComplianceMatrix() {
  const { data, isLoading, isError } = useCompliance();

  return (
    <Card
      variant="outlined"
      className="glass-panel"
      style={{ borderRadius: 14 }}
      styles={{ body: { padding: 22 } }}
      title={
        <Space>
          <DatabaseOutlined style={{ color: brand.green600 }} />
          <Text strong>Database compliance</Text>
          {data ? (
            <Tag color={data.compliant_count === data.total_count ? 'green' : 'orange'}>
              {data.compliant_count}/{data.total_count} ready
            </Tag>
          ) : null}
        </Space>
      }
    >
      {isLoading ? <Skeleton active paragraph={{ rows: 6 }} /> : null}
      {isError ? (
        <Text type="secondary">Could not load the compliance matrix from the backend.</Text>
      ) : null}
      {data ? (
        <Table<ComplianceEntry>
          size="small"
          rowKey="db_type"
          dataSource={data.entries}
          pagination={false}
          columns={[
            {
              title: 'Database',
              dataIndex: 'db_type',
              render: (dbType: string) => <Text code>{dbType}</Text>,
            },
            {
              title: 'Engine family',
              dataIndex: 'family',
              filters: [...new Set(data.entries.map((e) => e.family))].map((f) => ({
                text: f,
                value: f,
              })),
              onFilter: (value, e) => e.family === value,
              render: (family: string) => <Tag>{family}</Tag>,
            },
            {
              title: 'Driver',
              key: 'driver',
              render: (_, e) => (
                <Space size={6}>
                  <Text style={{ fontSize: 12.5 }}>{e.driver_package}</Text>
                  {e.driver_installed ? (
                    <Tag color="green">installed</Tag>
                  ) : (
                    <Tag color="red">missing</Tag>
                  )}
                </Space>
              ),
            },
            {
              title: 'As source',
              key: 'src',
              width: 130,
              render: (_, e) => <SupportTag ok={e.source_supported} />,
            },
            {
              title: 'As target',
              key: 'tgt',
              width: 130,
              render: (_, e) => <SupportTag ok={e.target_supported} />,
            },
            {
              title: 'Notes',
              dataIndex: 'notes',
              render: (notes: string) => (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {notes}
                </Text>
              ),
            },
          ]}
        />
      ) : null}
    </Card>
  );
}

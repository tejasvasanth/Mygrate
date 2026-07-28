import { Button, Card, Progress, Space, Table, Tag, Tooltip, Typography } from 'antd';
import { NodeIndexOutlined, RedoOutlined } from '@ant-design/icons';
import { brand } from '@/theme';
import type { TablePlanEntry, TablePlanResponse, TableStatus } from '@/types';

const { Text } = Typography;

const STATUS_TAG: Record<TableStatus, { color: string; label: string }> = {
  pending: { color: 'default', label: 'pending' },
  migrating: { color: 'processing', label: 'migrating' },
  migrated: { color: 'green', label: 'migrated' },
  validated: { color: 'green', label: 'validated' },
  skipped: { color: 'orange', label: 'skipped' },
};

/**
 * T2-4 — per-table progress in FK dependency order, plus the T2-3 resume
 * action. Tables are listed in the order they will load: parents first, so a
 * child never references a row that does not exist yet.
 */
export function TablePlanCard({
  plan,
  onResume,
  resuming,
  canResume,
}: {
  plan: TablePlanResponse;
  onResume?: (tables?: string[]) => void;
  resuming?: boolean;
  canResume?: boolean;
}) {
  const incomplete = plan.tables.filter(
    (t) => t.status !== 'migrated' && t.status !== 'validated' && t.status !== 'skipped',
  );

  return (
    <Card
      variant="outlined"
      className="glass-panel"
      style={{ borderRadius: 14 }}
      styles={{ body: { padding: 22 } }}
      title={
        <Space>
          <NodeIndexOutlined style={{ color: brand.green600 }} />
          <Text strong>Tables — load order</Text>
          <Tooltip title="Parents load before children so foreign keys always resolve.">
            <Tag>{plan.tables.length} tables</Tag>
          </Tooltip>
        </Space>
      }
      extra={
        onResume && canResume && incomplete.length > 0 ? (
          <Button
            size="small"
            icon={<RedoOutlined />}
            loading={resuming}
            onClick={() => onResume()}
          >
            Resume {incomplete.length} remaining
          </Button>
        ) : null
      }
    >
      <Table<TablePlanEntry>
        size="small"
        rowKey="table"
        dataSource={plan.tables}
        pagination={false}
        columns={[
          {
            title: '#',
            dataIndex: 'order',
            key: 'order',
            width: 50,
            render: (o: number) => <Text type="secondary">{o + 1}</Text>,
          },
          {
            title: 'Table',
            key: 'table',
            render: (_, t) => (
              <Space direction="vertical" size={0}>
                <Text strong>{t.table}</Text>
                {t.target_table !== t.table ? (
                  <Text type="secondary" style={{ fontSize: 11.5 }}>
                    → {t.target_table}
                  </Text>
                ) : null}
              </Space>
            ),
          },
          {
            title: 'Depends on',
            dataIndex: 'depends_on',
            key: 'depends_on',
            render: (deps: string[]) =>
              deps.length ? (
                <Space size={4} wrap>
                  {deps.map((d) => (
                    <Tag key={d}>{d}</Tag>
                  ))}
                </Space>
              ) : (
                <Text type="secondary">—</Text>
              ),
          },
          {
            title: 'Progress',
            key: 'progress',
            width: 200,
            render: (_, t) => {
              const pct = t.estimated_rows
                ? Math.min(100, Math.round((100 * t.rows_committed) / t.estimated_rows))
                : t.status === 'migrated' || t.status === 'validated'
                  ? 100
                  : 0;
              return (
                <Space direction="vertical" size={0} style={{ width: '100%' }}>
                  <Progress
                    percent={pct}
                    size="small"
                    strokeColor={brand.green600}
                    showInfo={false}
                  />
                  <Text type="secondary" style={{ fontSize: 11.5 }}>
                    {t.rows_committed.toLocaleString()} /{' '}
                    {t.estimated_rows.toLocaleString()} rows
                  </Text>
                </Space>
              );
            },
          },
          {
            title: 'Status',
            dataIndex: 'status',
            key: 'status',
            width: 120,
            render: (s: TableStatus) => (
              <Tag color={STATUS_TAG[s].color}>{STATUS_TAG[s].label}</Tag>
            ),
          },
        ]}
      />
    </Card>
  );
}

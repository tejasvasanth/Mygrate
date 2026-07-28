import { Card, Progress, Space, Table, Tag, Typography } from 'antd';
import { SafetyCertificateOutlined, WarningFilled } from '@ant-design/icons';
import { brand } from '@/theme';
import type {
  ColumnConfidence,
  ConfidenceBreakdown as ConfidenceBreakdownData,
  TableConfidence,
} from '@/types';

const { Text } = Typography;

function confColor(value: number, threshold: number): string {
  if (value >= threshold) return brand.green600;
  return value >= threshold - 15 ? '#F59E0B' : '#DC2626';
}

/** Per-table confidence with expandable per-column detail; <90% is flagged. */
export function ConfidenceBreakdown({ breakdown }: { breakdown: ConfidenceBreakdownData }) {
  const t = breakdown.review_threshold;
  return (
    <Card
      variant="outlined"
      className="glass-panel"
      style={{ borderRadius: 14 }}
      styles={{ body: { padding: 22 } }}
      title={
        <Space>
          <SafetyCertificateOutlined style={{ color: brand.green600 }} />
          <Text strong>Confidence breakdown</Text>
          {breakdown.flagged_columns.length > 0 ? (
            <Tag color="orange" icon={<WarningFilled />}>
              {breakdown.flagged_columns.length} column(s) under {t}% — manual review
            </Tag>
          ) : (
            <Tag color="green">all columns at or above {t}%</Tag>
          )}
        </Space>
      }
    >
      <Table<TableConfidence>
        size="small"
        rowKey="table"
        dataSource={breakdown.tables}
        pagination={false}
        expandable={{
          defaultExpandedRowKeys: breakdown.tables
            .filter((row) => row.needs_review || row.columns.some((c) => c.needs_review))
            .map((row) => row.table),
          expandedRowRender: (row) => (
            <Table<ColumnConfidence>
              size="small"
              rowKey="column"
              dataSource={row.columns}
              pagination={false}
              columns={[
                {
                  title: 'Column',
                  dataIndex: 'column',
                  render: (c: string) => <Text code>{c}</Text>,
                },
                {
                  title: 'Confidence',
                  key: 'conf',
                  width: 220,
                  render: (_, c) => (
                    <Progress
                      percent={c.confidence}
                      size="small"
                      strokeColor={confColor(c.confidence, t)}
                      format={(p) => `${p}%`}
                    />
                  ),
                },
                {
                  title: 'Status',
                  key: 'status',
                  width: 140,
                  render: (_, c) =>
                    c.needs_review ? (
                      <Tag color="red">manual review</Tag>
                    ) : (
                      <Tag color="green">ok</Tag>
                    ),
                },
                {
                  title: 'Why',
                  key: 'reasons',
                  render: (_, c) =>
                    c.reasons.length ? (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {c.reasons.join('; ')}
                      </Text>
                    ) : (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        —
                      </Text>
                    ),
                },
              ]}
            />
          ),
        }}
        columns={[
          {
            title: 'Table',
            dataIndex: 'table',
            render: (name: string) => <Text strong>{name}</Text>,
          },
          {
            title: 'Confidence',
            key: 'conf',
            width: 240,
            render: (_, row) => (
              <Progress
                percent={row.confidence}
                size="small"
                strokeColor={confColor(row.confidence, t)}
              />
            ),
          },
          {
            title: 'Row count',
            key: 'rc',
            width: 110,
            render: (_, row) =>
              row.components.row_count ? (
                <Tag color="green">match</Tag>
              ) : (
                <Tag color="red">mismatch</Tag>
              ),
          },
          {
            title: 'Hash match',
            key: 'hash',
            width: 110,
            render: (_, row) => {
              const pct = Math.round(row.components.sample_hash_ratio * 100);
              return <Tag color={pct === 100 ? 'green' : 'orange'}>{pct}%</Tag>;
            },
          },
          {
            title: 'FK integrity',
            key: 'fk',
            width: 110,
            render: (_, row) =>
              row.components.fk_integrity ? (
                <Tag color="green">ok</Tag>
              ) : (
                <Tag color="red">broken</Tag>
              ),
          },
        ]}
      />
    </Card>
  );
}

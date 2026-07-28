import { Card, Col, Progress, Row, Space, Statistic, Table, Tag, Typography } from 'antd';
import { SafetyOutlined, WarningFilled } from '@ant-design/icons';
import { brand } from '@/theme';
import type { DataQualityReport, QualityIssue, QualitySeverity } from '@/types';

const { Text } = Typography;

const RED = '#DC2626';
const AMBER = '#F59E0B';

const severityColor: Record<QualitySeverity, string> = {
  high: 'red',
  medium: 'orange',
  low: 'blue',
};

const KIND_LABEL: Record<string, string> = {
  duplicate_in_unique: 'Duplicate in UNIQUE column',
  empty_string_in_not_null: "Empty string where NULL was meant",
  sentinel_date: 'Sentinel date value',
  numeric_sentinel: 'Numeric sentinel value',
  orphaned_rows: 'Orphaned rows',
};

function scoreColor(score: number): string {
  if (score >= 85) return brand.green600;
  return score >= 60 ? AMBER : RED;
}

/**
 * T1-5 — what is already broken in the SOURCE. Shown before migration so the
 * engineer fixes it there rather than discovering it in the target.
 */
export function QualityReportCard({ report }: { report: DataQualityReport }) {
  const { quality_score: score, counts } = report;
  const tiles: Array<{ label: string; value: number; color: string }> = [
    { label: 'High severity', value: counts.high ?? 0, color: RED },
    { label: 'Medium severity', value: counts.medium ?? 0, color: AMBER },
    { label: 'Low severity', value: counts.low ?? 0, color: brand.green600 },
    { label: 'Tables checked', value: report.tables_checked, color: brand.inkSoft },
  ];

  return (
    <Card
      variant="outlined"
      className="glass-panel"
      style={{ borderRadius: 14 }}
      styles={{ body: { padding: 22 } }}
      title={
        <Space>
          <SafetyOutlined style={{ color: brand.green600 }} />
          <Text strong>Source data quality</Text>
          {report.issues.length > 0 ? (
            <Tag color={counts.high ? 'red' : 'orange'} icon={<WarningFilled />}>
              {report.issues.length} issue{report.issues.length === 1 ? '' : 's'} found
            </Tag>
          ) : (
            <Tag color="green">no issues found</Tag>
          )}
        </Space>
      }
    >
      <Row gutter={[20, 20]} align="middle">
        <Col xs={24} md={7}>
          <Space direction="vertical" size={4} align="center" style={{ width: '100%' }}>
            <Progress
              type="dashboard"
              percent={score}
              size={150}
              strokeColor={scoreColor(score)}
              format={(p) => (
                <span style={{ fontSize: 34, fontWeight: 700, color: scoreColor(score) }}>
                  {p}
                </span>
              )}
            />
            <Text strong style={{ fontSize: 13.5 }}>
              Data quality score
            </Text>
          </Space>
        </Col>
        <Col xs={24} md={17}>
          <Row gutter={[12, 12]}>
            {tiles.map((t) => (
              <Col xs={12} md={6} key={t.label}>
                <Card
                  variant="outlined"
                  styles={{ body: { padding: 14 } }}
                  style={{ borderRadius: 10, borderLeft: `3px solid ${t.color}` }}
                >
                  <Statistic
                    title={<Text style={{ fontSize: 12, color: brand.inkMuted }}>{t.label}</Text>}
                    value={t.value}
                    valueStyle={{ fontSize: 22, fontWeight: 650, color: t.color }}
                  />
                </Card>
              </Col>
            ))}
          </Row>
          {report.issues.length === 0 ? (
            <Text type="secondary" style={{ fontSize: 13, display: 'block', marginTop: 14 }}>
              No referential-integrity violations, duplicates, sentinel values or
              orphaned rows were found in the sample. Your source is clean.
            </Text>
          ) : null}
        </Col>
      </Row>

      {report.issues.length > 0 ? (
        <Table<QualityIssue>
          size="small"
          style={{ marginTop: 20 }}
          rowKey={(i, index) => `${i.table}.${i.column ?? ''}.${i.kind}.${index}`}
          dataSource={report.issues}
          pagination={report.issues.length > 15 ? { pageSize: 15 } : false}
          columns={[
            {
              title: 'Severity',
              dataIndex: 'severity',
              key: 'severity',
              width: 110,
              filters: (['high', 'medium', 'low'] as QualitySeverity[]).map((s) => ({
                text: s,
                value: s,
              })),
              onFilter: (value, i) => i.severity === value,
              render: (s: QualitySeverity) => (
                <Tag color={severityColor[s]}>{s.toUpperCase()}</Tag>
              ),
            },
            {
              title: 'Where',
              key: 'where',
              render: (_, i) => (
                <Text code>{i.column ? `${i.table}.${i.column}` : i.table}</Text>
              ),
            },
            {
              title: 'Problem',
              dataIndex: 'kind',
              key: 'kind',
              render: (k: string) => <Text>{KIND_LABEL[k] ?? k}</Text>,
            },
            {
              title: 'Detail',
              dataIndex: 'detail',
              key: 'detail',
              render: (d: string) => (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {d}
                </Text>
              ),
            },
          ]}
        />
      ) : null}
    </Card>
  );
}

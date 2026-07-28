import { useParams } from 'react-router-dom';
import {
  Card,
  Col,
  Progress,
  Result,
  Row,
  Skeleton,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import { CheckCircleFilled, ClockCircleOutlined } from '@ant-design/icons';
import { DbPair } from '@/components/migration/DbBadge';
import { usePublicReport } from '@/hooks/useMigration';
import { brand } from '@/theme';
import type { PublicReport as PublicReportData } from '@/types';

const { Text, Title, Paragraph } = Typography;

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

/**
 * T3-2 — the shareable, redacted report at /r/:token. No auth: everything
 * shown here is what the job owner explicitly chose to publish.
 */
export function PublicReport() {
  const { token } = useParams<{ token: string }>();
  const { data: report, isLoading, isError } = usePublicReport(token);

  if (isLoading) {
    return (
      <Card variant="outlined" className="glass-panel" style={{ borderRadius: 14 }}>
        <Skeleton active paragraph={{ rows: 8 }} />
      </Card>
    );
  }

  if (isError || !report) {
    return (
      <Result
        status="404"
        title="Report not found"
        subTitle="This link is invalid, or the report has been made private by its owner."
      />
    );
  }

  const mismatches = report.semantic_mismatches_caught;
  const savedHours = Math.max(
    0,
    report.estimated_manual_hours - (report.duration_seconds ?? 0) / 3600,
  );

  return (
    <Space direction="vertical" size={20} style={{ width: '100%' }}>
      <Space direction="vertical" size={8}>
        <Space size={10} align="center">
          <CheckCircleFilled style={{ color: brand.green600, fontSize: 20 }} />
          <Title level={3} style={{ margin: 0, letterSpacing: '-0.02em' }}>
            Migration complete
          </Title>
        </Space>
        <DbPair source={report.source_db_type} target={report.target_db_type} />
        {report.completed_at ? (
          <Text type="secondary" style={{ fontSize: 12.5 }}>
            Completed {new Date(report.completed_at).toLocaleString()}
          </Text>
        ) : null}
      </Space>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card
            variant="outlined"
            className="glass-panel"
            style={{ borderRadius: 14, height: '100%' }}
            styles={{ body: { padding: 22 } }}
          >
            <Space direction="vertical" size={4} align="center" style={{ width: '100%' }}>
              <Progress
                type="dashboard"
                percent={report.confidence_score}
                size={150}
                strokeColor={
                  report.confidence_score >= 90 ? brand.green600 : '#F59E0B'
                }
                format={(p) => (
                  <span style={{ fontSize: 32, fontWeight: 700 }}>{p}%</span>
                )}
              />
              <Text strong>Validation confidence</Text>
            </Space>
          </Card>
        </Col>
        <Col xs={24} md={16}>
          <Row gutter={[16, 16]}>
            {[
              { label: 'Tables migrated', value: report.tables_migrated },
              {
                label: 'Rows migrated',
                value: report.rows_migrated.toLocaleString(),
              },
              {
                label: 'Semantic issues caught',
                value: mismatches.total,
              },
              {
                label: 'Schema trust score',
                value: report.schema_trust_score ?? '—',
              },
            ].map((s) => (
              <Col xs={12} key={s.label}>
                <Card
                  variant="outlined"
                  className="glass-panel"
                  style={{ borderRadius: 12 }}
                  styles={{ body: { padding: 18 } }}
                >
                  <Statistic
                    title={
                      <Text style={{ fontSize: 12, color: brand.inkMuted }}>{s.label}</Text>
                    }
                    value={s.value}
                    valueStyle={{ fontSize: 24, fontWeight: 650 }}
                  />
                </Card>
              </Col>
            ))}
          </Row>
        </Col>
      </Row>

      <Card
        variant="outlined"
        className="glass-panel"
        style={{ borderRadius: 14 }}
        styles={{ body: { padding: 22 } }}
        title={<Text strong>Time</Text>}
      >
        <Row gutter={[20, 20]}>
          <Col xs={24} md={8}>
            <Statistic
              title={<Text style={{ fontSize: 12.5 }}>Migrate took</Text>}
              value={formatDuration(report.duration_seconds)}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ fontSize: 22, fontWeight: 650, color: brand.green600 }}
            />
          </Col>
          <Col xs={24} md={8}>
            <Statistic
              title={<Text style={{ fontSize: 12.5 }}>Estimated by hand</Text>}
              value={`${report.estimated_manual_hours}h`}
              valueStyle={{ fontSize: 22, fontWeight: 650 }}
            />
          </Col>
          <Col xs={24} md={8}>
            <Statistic
              title={<Text style={{ fontSize: 12.5 }}>Time saved</Text>}
              value={`~${savedHours.toFixed(1)}h`}
              valueStyle={{ fontSize: 22, fontWeight: 650, color: brand.green600 }}
            />
          </Col>
        </Row>
      </Card>

      <Card
        variant="outlined"
        className="glass-panel"
        style={{ borderRadius: 14 }}
        styles={{ body: { padding: 22 } }}
        title={<Text strong>Semantic mismatches caught before migrating</Text>}
      >
        <Space size={8} wrap>
          {[
            ['Implicit booleans', mismatches.implicit_booleans],
            ['Implicit enums', mismatches.implicit_enums],
            ['Never-null nullables', mismatches.never_null_nullables],
            ['Dangerous type mismatches', mismatches.dangerous_type_mismatches],
            ['Undeclared foreign keys', mismatches.implicit_foreign_keys],
            ['PII columns', mismatches.pii_columns],
          ].map(([label, count]) => (
            <Tag
              key={String(label)}
              color={Number(count) > 0 ? 'green' : 'default'}
              style={{ padding: '4px 10px', fontSize: 12.5 }}
            >
              {label}: <strong>{count}</strong>
            </Tag>
          ))}
        </Space>
      </Card>

      <Card
        variant="outlined"
        className="glass-panel"
        style={{ borderRadius: 14 }}
        styles={{ body: { padding: 22 } }}
        title={
          <Space>
            <Text strong>Per-table results</Text>
            {report.names_redacted ? <Tag>names redacted</Tag> : null}
          </Space>
        }
      >
        <Table<PublicReportData['tables'][number]>
          size="small"
          rowKey="table"
          dataSource={report.tables}
          pagination={false}
          columns={[
            { title: 'Table', dataIndex: 'table', key: 'table' },
            {
              title: 'Source rows',
              dataIndex: 'source_rows',
              key: 'src',
              render: (v: number | null) => (v ?? '—').toLocaleString?.() ?? '—',
            },
            {
              title: 'Target rows',
              dataIndex: 'target_rows',
              key: 'tgt',
              render: (v: number | null) => (v ?? '—').toLocaleString?.() ?? '—',
            },
            {
              title: 'Row counts',
              dataIndex: 'row_count_ok',
              key: 'ok',
              render: (ok: boolean | null) =>
                ok === null ? (
                  <Text type="secondary">—</Text>
                ) : ok ? (
                  <Tag color="green">match</Tag>
                ) : (
                  <Tag color="red">mismatch</Tag>
                ),
            },
          ]}
        />
      </Card>

      <Paragraph type="secondary" style={{ fontSize: 12, textAlign: 'center' }}>
        Generated by Migrate. Connection strings, credentials and column names are
        never included in a shared report.
      </Paragraph>
    </Space>
  );
}

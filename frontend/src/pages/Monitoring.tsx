import { useState } from 'react';
import {
  App as AntApp,
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Popconfirm,
  Progress,
  Row,
  Skeleton,
  Space,
  Table,
  Tag,
  Timeline,
  Typography,
} from 'antd';
import {
  BellOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  MonitorOutlined,
  ReloadOutlined,
  WarningFilled,
} from '@ant-design/icons';
import { DbChip } from '@/components/migration/DbBadge';
import {
  useDeleteMonitor,
  useDrift,
  useHealthReport,
  useMonitors,
  useRebaseline,
  useRunDriftCheck,
} from '@/hooks/useMigration';
import { apiErrorMessage } from '@/lib/api';
import { brand } from '@/theme';
import type { DriftEvent, DriftSeverity, Monitor } from '@/types';

const { Text, Title, Paragraph } = Typography;

const RED = '#DC2626';
const AMBER = '#F59E0B';

const severityColor: Record<DriftSeverity, string> = {
  critical: 'red',
  warning: 'orange',
  info: 'blue',
};

function healthColor(score: number): string {
  if (score >= 85) return brand.green600;
  return score >= 60 ? AMBER : RED;
}

export function Monitoring() {
  const { message } = AntApp.useApp();
  const { data: monitors, isLoading } = useMonitors();
  const [selected, setSelected] = useState<string | undefined>();
  const active = selected ?? monitors?.[0]?.id;

  const { data: drift } = useDrift(active);
  const { data: health } = useHealthReport(active);
  const runCheck = useRunDriftCheck();
  const rebaseline = useRebaseline();
  const deleteMonitor = useDeleteMonitor();

  if (isLoading) {
    return (
      <Card variant="outlined" className="glass-panel" style={{ borderRadius: 14 }}>
        <Skeleton active paragraph={{ rows: 6 }} />
      </Card>
    );
  }

  if (!monitors || monitors.length === 0) {
    return (
      <Space direction="vertical" size={24} style={{ width: '100%' }}>
        <div>
          <Title level={3} style={{ margin: 0, letterSpacing: '-0.02em' }}>
            Drift monitoring
          </Title>
          <Text type="secondary" style={{ fontSize: 13.5 }}>
            Watch a migrated database for schema changes after the migration.
          </Text>
        </div>
        <Card variant="outlined" className="glass-panel" style={{ borderRadius: 14 }}>
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <Space direction="vertical" size={6}>
                <Text>No databases are being monitored yet.</Text>
                <Text type="secondary" style={{ fontSize: 12.5 }}>
                  Open a completed migration and choose "Monitor for drift" to take a
                  baseline of the target schema. Migrate then checks it daily and
                  alerts you when columns, types or constraints change.
                </Text>
              </Space>
            }
          />
        </Card>
      </Space>
    );
  }

  const current = monitors.find((m) => m.id === active);
  const latest = drift?.latest;

  return (
    <Space direction="vertical" size={20} style={{ width: '100%' }}>
      <div>
        <Title level={3} style={{ margin: 0, letterSpacing: '-0.02em' }}>
          Drift monitoring
        </Title>
        <Text type="secondary" style={{ fontSize: 13.5 }}>
          Migrate checks each monitored database daily and compares it against the
          baseline taken at migration time.
        </Text>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={9}>
          <Card
            variant="outlined"
            className="glass-panel"
            style={{ borderRadius: 14 }}
            styles={{ body: { padding: 12 } }}
            title={
              <Space>
                <MonitorOutlined style={{ color: brand.green600 }} />
                <Text strong>Monitored databases</Text>
              </Space>
            }
          >
            <Table<Monitor>
              size="small"
              rowKey="id"
              dataSource={monitors}
              pagination={false}
              showHeader={false}
              onRow={(m) => ({
                onClick: () => setSelected(m.id),
                style: {
                  cursor: 'pointer',
                  background: m.id === active ? 'rgba(22,163,74,0.06)' : undefined,
                },
              })}
              columns={[
                {
                  key: 'name',
                  render: (_, m) => (
                    <Space direction="vertical" size={2}>
                      <Space size={8}>
                        <Text strong>{m.name}</Text>
                        <DbChip type={m.target_db_type} size="small" />
                        {!m.enabled ? <Tag>paused</Tag> : null}
                      </Space>
                      <Text type="secondary" style={{ fontSize: 11.5 }}>
                        {m.baseline_table_count} tables ·{' '}
                        {m.last_checked_at
                          ? `checked ${new Date(m.last_checked_at).toLocaleString()}`
                          : 'never checked'}
                      </Text>
                    </Space>
                  ),
                },
                {
                  key: 'score',
                  width: 70,
                  align: 'right',
                  render: (_, m) => (
                    <Text
                      strong
                      style={{ color: healthColor(m.last_health_score ?? 100) }}
                    >
                      {m.last_health_score ?? 100}
                    </Text>
                  ),
                },
              ]}
            />
          </Card>
        </Col>

        <Col xs={24} lg={15}>
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            {current ? (
              <Card
                variant="outlined"
                className="glass-panel"
                style={{ borderRadius: 14 }}
                styles={{ body: { padding: 22 } }}
                title={<Text strong>{current.name}</Text>}
                extra={
                  <Space>
                    <Button
                      size="small"
                      icon={<ReloadOutlined />}
                      loading={runCheck.isPending}
                      onClick={() =>
                        runCheck.mutate(current.id, {
                          onSuccess: (r: { has_drift: boolean }) =>
                            message[r.has_drift ? 'warning' : 'success'](
                              r.has_drift
                                ? 'Drift detected'
                                : 'No drift — schema matches baseline',
                            ),
                          onError: (e) => message.error(apiErrorMessage(e)),
                        })
                      }
                    >
                      Check now
                    </Button>
                    <Popconfirm
                      title="Accept the current schema as the new baseline?"
                      description="Existing drift will be cleared and future checks compare against today's schema."
                      onConfirm={() =>
                        rebaseline.mutate(current.id, {
                          onSuccess: () => message.success('Baseline updated'),
                          onError: (e) => message.error(apiErrorMessage(e)),
                        })
                      }
                    >
                      <Button size="small" icon={<CheckCircleOutlined />}>
                        Re-baseline
                      </Button>
                    </Popconfirm>
                    <Popconfirm
                      title="Stop monitoring this database?"
                      onConfirm={() =>
                        deleteMonitor.mutate(current.id, {
                          onSuccess: () => {
                            setSelected(undefined);
                            message.success('Monitoring stopped');
                          },
                          onError: (e) => message.error(apiErrorMessage(e)),
                        })
                      }
                    >
                      <Button size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  </Space>
                }
              >
                <Row gutter={[20, 20]} align="middle">
                  <Col xs={24} md={8}>
                    <Space
                      direction="vertical"
                      size={4}
                      align="center"
                      style={{ width: '100%' }}
                    >
                      <Progress
                        type="dashboard"
                        percent={latest?.health_score ?? current.last_health_score ?? 100}
                        size={140}
                        strokeColor={healthColor(
                          latest?.health_score ?? current.last_health_score ?? 100,
                        )}
                        format={(p) => (
                          <span style={{ fontSize: 30, fontWeight: 700 }}>{p}</span>
                        )}
                      />
                      <Text strong style={{ fontSize: 13 }}>
                        Health score
                      </Text>
                    </Space>
                  </Col>
                  <Col xs={24} md={16}>
                    {health ? (
                      <Space direction="vertical" size={8}>
                        <Text strong style={{ fontSize: 15 }}>
                          {health.headline}
                        </Text>
                        <Text type="secondary" style={{ fontSize: 12.5 }}>
                          {health.checks_run} check(s) · {health.drift_events} drift
                          event(s) · {health.critical_events} critical
                        </Text>
                        {health.recommendations.map((r) => (
                          <Text key={r} style={{ fontSize: 12.5 }}>
                            • {r}
                          </Text>
                        ))}
                      </Space>
                    ) : null}
                    <Space size={6} wrap style={{ marginTop: 12 }}>
                      <BellOutlined style={{ color: brand.inkMuted }} />
                      {current.alerts_configured.email ? <Tag color="green">email</Tag> : null}
                      {current.alerts_configured.slack ? <Tag color="green">Slack</Tag> : null}
                      {current.alerts_configured.pagerduty ? (
                        <Tag color="green">PagerDuty</Tag>
                      ) : null}
                      {!current.alerts_configured.email &&
                      !current.alerts_configured.slack &&
                      !current.alerts_configured.pagerduty ? (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          no alert channels configured
                        </Text>
                      ) : null}
                    </Space>
                  </Col>
                </Row>
              </Card>
            ) : null}

            {latest?.error ? (
              <Alert
                type="error"
                showIcon
                message="The last drift check failed"
                description={latest.error}
              />
            ) : null}

            {latest && latest.events && latest.events.length > 0 ? (
              <Card
                variant="outlined"
                className="glass-panel"
                style={{ borderRadius: 14 }}
                styles={{ body: { padding: 22 } }}
                title={
                  <Space>
                    <WarningFilled style={{ color: RED }} />
                    <Text strong>Drift detected</Text>
                    <Tag color="red">{latest.counts.critical ?? 0} critical</Tag>
                    <Tag color="orange">{latest.counts.warning ?? 0} warning</Tag>
                  </Space>
                }
              >
                <Table<DriftEvent>
                  size="small"
                  rowKey={(e, i) => `${e.table}.${e.column ?? ''}.${e.kind}.${i}`}
                  dataSource={latest.events}
                  pagination={latest.events.length > 12 ? { pageSize: 12 } : false}
                  expandable={{
                    rowExpandable: (e) => Boolean(e.semantic_regression),
                    expandedRowRender: (e) =>
                      e.semantic_regression ? (
                        <Paragraph style={{ margin: 0, fontSize: 12.5 }}>
                          Based on your migration history this looks like a{' '}
                          <Text strong>{e.semantic_regression.likely_semantic_type}</Text>{' '}
                          column. Recommend{' '}
                          <Text strong>{e.semantic_regression.recommendation}</Text>.
                        </Paragraph>
                      ) : null,
                  }}
                  columns={[
                    {
                      title: 'Severity',
                      dataIndex: 'severity',
                      key: 'severity',
                      width: 110,
                      render: (s: DriftSeverity) => (
                        <Tag color={severityColor[s]}>{s.toUpperCase()}</Tag>
                      ),
                    },
                    {
                      title: 'Where',
                      key: 'where',
                      render: (_, e) => (
                        <Text code>{e.column ? `${e.table}.${e.column}` : e.table}</Text>
                      ),
                    },
                    {
                      title: 'What changed',
                      dataIndex: 'detail',
                      key: 'detail',
                    },
                  ]}
                />
              </Card>
            ) : latest ? (
              <Alert
                type="success"
                showIcon
                message="No drift"
                description="The schema matches the baseline taken at migration time."
              />
            ) : null}

            {drift && drift.timeline.length > 0 ? (
              <Card
                variant="outlined"
                className="glass-panel"
                style={{ borderRadius: 14 }}
                styles={{ body: { padding: 22 } }}
                title={<Text strong>Check history</Text>}
              >
                <Timeline
                  items={drift.timeline.map((c) => ({
                    color: c.error
                      ? 'gray'
                      : c.has_drift
                        ? (c.counts.critical ?? 0) > 0
                          ? 'red'
                          : 'orange'
                        : 'green',
                    children: (
                      <Space direction="vertical" size={0}>
                        <Text style={{ fontSize: 12.5 }}>
                          {c.checked_at ? new Date(c.checked_at).toLocaleString() : '—'}
                        </Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {c.error
                            ? `check failed: ${c.error}`
                            : c.has_drift
                              ? `${c.counts.critical ?? 0} critical, ${c.counts.warning ?? 0} warning · health ${c.health_score}`
                              : `no drift · health ${c.health_score}`}
                        </Text>
                      </Space>
                    ),
                  }))}
                />
              </Card>
            ) : null}
          </Space>
        </Col>
      </Row>
    </Space>
  );
}

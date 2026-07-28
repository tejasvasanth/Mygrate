import { useState } from 'react';
import {
  App as AntApp,
  Button,
  Card,
  Col,
  Empty,
  List,
  Progress,
  Row,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import { FilePdfOutlined, FlagOutlined, RobotOutlined } from '@ant-design/icons';
import { api, apiErrorMessage } from '@/lib/api';
import { brand } from '@/theme';
import type { FinalReport, FlagSeverity } from '@/types';

const { Text, Paragraph } = Typography;

const severityColor: Record<FlagSeverity, string> = {
  high: 'red',
  medium: 'orange',
  low: 'blue',
};

export function FinalReportCard({
  jobId,
  jobName,
  report,
}: {
  jobId: string;
  jobName: string;
  report: FinalReport;
}) {
  const { message } = AntApp.useApp();
  const [downloading, setDownloading] = useState(false);

  const downloadPdf = async () => {
    setDownloading(true);
    try {
      const res = await api.get<Blob>(`/migrations/${jobId}/report/pdf`, {
        responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${jobName.replace(/\s+/g, '_')}_report.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      message.error(apiErrorMessage(e));
    } finally {
      setDownloading(false);
    }
  };

  const breakdown = report.confidence_explanation?.breakdown ?? [];

  return (
    <Card
      variant="outlined"
      className="glass-panel"
      style={{ borderRadius: 14 }}
      styles={{ body: { padding: 22 } }}
      title={
        <Space>
          <Text strong>Final report</Text>
          {report.ai_generated ? (
            <Tag icon={<RobotOutlined />} color="green">
              AI-written
            </Tag>
          ) : (
            <Tag>Rule-based</Tag>
          )}
        </Space>
      }
      extra={
        <Button
          type="primary"
          icon={<FilePdfOutlined />}
          loading={downloading}
          onClick={downloadPdf}
        >
          Download PDF
        </Button>
      }
    >
      <Space direction="vertical" size={18} style={{ width: '100%' }}>
        <Paragraph style={{ margin: 0, fontSize: 13.5 }}>
          {report.executive_summary}
        </Paragraph>

        {report.confidence_explanation?.narrative ? (
          <div>
            <Text strong style={{ fontSize: 13 }}>
              Why the score is {report.confidence_score}%
            </Text>
            <Paragraph style={{ margin: '6px 0 0', fontSize: 13, color: brand.inkSoft }}>
              {report.confidence_explanation.narrative}
            </Paragraph>
          </div>
        ) : null}

        {breakdown.length > 0 ? (
          <Row gutter={[16, 16]}>
            {breakdown.map((b) => (
              <Col xs={24} md={8} key={b.component}>
                <Card size="small" variant="outlined" style={{ borderRadius: 10 }}>
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                      <Text strong style={{ fontSize: 12.5 }}>
                        {b.component}
                      </Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        weight {b.weight}
                      </Text>
                    </Space>
                    <Progress
                      percent={b.score}
                      size="small"
                      strokeColor={b.score >= 90 ? brand.green600 : '#F59E0B'}
                    />
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {b.reason}
                    </Text>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        ) : null}

        <div>
          <Space size={6} style={{ marginBottom: 8 }}>
            <FlagOutlined />
            <Text strong style={{ fontSize: 13 }}>
              Flags to check ({report.flags.length})
            </Text>
          </Space>
          {report.flags.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="No flags — all checks passed"
            />
          ) : (
            <Table
              size="small"
              rowKey={(f) => `${f.severity}-${f.table}-${f.title}-${f.detail}`}
              pagination={report.flags.length > 8 ? { pageSize: 8 } : false}
              dataSource={report.flags}
              columns={[
                {
                  title: 'Severity',
                  dataIndex: 'severity',
                  width: 90,
                  render: (s: FlagSeverity) => (
                    <Tag color={severityColor[s]}>{s.toUpperCase()}</Tag>
                  ),
                },
                { title: 'Table', dataIndex: 'table', width: 130, render: (t) => t ?? '—' },
                { title: 'Issue', dataIndex: 'title', width: 200 },
                {
                  title: 'Detail & what to check',
                  key: 'detail',
                  render: (_, f) => (
                    <Space direction="vertical" size={2}>
                      <Text style={{ fontSize: 12.5 }}>{f.detail}</Text>
                      {f.what_to_check ? (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          Check: {f.what_to_check}
                        </Text>
                      ) : null}
                    </Space>
                  ),
                },
              ]}
            />
          )}
        </div>

        {report.recommendations.length > 0 ? (
          <div>
            <Text strong style={{ fontSize: 13 }}>
              Recommendations
            </Text>
            <List
              size="small"
              dataSource={report.recommendations}
              renderItem={(r) => (
                <List.Item style={{ padding: '4px 0', border: 'none', fontSize: 13 }}>
                  • {r}
                </List.Item>
              )}
            />
          </div>
        ) : null}
      </Space>
    </Card>
  );
}

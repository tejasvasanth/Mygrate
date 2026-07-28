import { useNavigate } from 'react-router-dom';
import { Card, Progress, Space, Tooltip, Typography } from 'antd';
import { ClockCircleOutlined, DatabaseOutlined } from '@ant-design/icons';
import { StatusBadge } from './StatusBadge';
import { DbPair } from './DbBadge';
import { AnimatedNumber } from '@/components/ui/AnimatedNumber';
import { brand, statusColor } from '@/theme';
import { duration, formatFullNumber, isActive, timeAgo } from '@/lib/utils';
import type { MigrationJob } from '@/types';

const { Text, Title } = Typography;

export function MigrationCard({ job }: { job: MigrationJob }) {
  const navigate = useNavigate();
  const running = isActive(job.status);

  return (
    <Card
      variant="outlined"
      className="hover-lift glass-panel"
      styles={{ body: { padding: 20 } }}
      style={{ borderRadius: 14, cursor: 'pointer', height: '100%' }}
      onClick={() => navigate(`/migrations/${job.id}`)}
    >
      <Space direction="vertical" size={14} style={{ width: '100%' }}>
        <Space
          align="start"
          style={{ width: '100%', justifyContent: 'space-between' }}
        >
          <Space direction="vertical" size={6}>
            <Title level={5} style={{ margin: 0, fontSize: 15.5, lineHeight: 1.35 }}>
              {job.name}
            </Title>
            <DbPair source={job.source_db_type} target={job.target_db_type} size="small" />
          </Space>
          <StatusBadge status={job.status} showLabel={false} />
        </Space>

        <div>
          <Space
            style={{ width: '100%', justifyContent: 'space-between', marginBottom: 6 }}
          >
            <Text style={{ fontSize: 12.5, color: brand.inkSoft }}>
              <DatabaseOutlined style={{ marginRight: 6 }} />
              <AnimatedNumber value={job.rows_migrated} format={(v) => formatFullNumber(Math.round(v))} />
              {' / '}
              {formatFullNumber(job.rows_total)} rows
            </Text>
            <Text strong style={{ fontSize: 12.5, color: statusColor[job.status] }}>
              <AnimatedNumber value={job.progress_pct} format={(v) => `${Math.round(v)}%`} />
            </Text>
          </Space>

          <Progress
            percent={job.progress_pct}
            showInfo={false}
            size="small"
            strokeColor={statusColor[job.status]}
            trailColor={brand.surfaceSoft}
            status={running ? 'active' : job.status === 'failed' ? 'exception' : 'normal'}
          />
        </div>

        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Tooltip title={new Date(job.created_at).toLocaleString()}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <ClockCircleOutlined style={{ marginRight: 5 }} />
              {timeAgo(job.created_at)}
            </Text>
          </Tooltip>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {job.started_at ? duration(job.started_at, job.completed_at) : 'Not started'}
          </Text>
        </Space>
      </Space>
    </Card>
  );
}

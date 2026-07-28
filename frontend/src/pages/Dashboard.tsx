import { useNavigate } from 'react-router-dom';
import { Button, Col, Empty, Row, Skeleton, Space, Statistic, Typography, Card } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { MigrationCard } from '@/components/migration/MigrationCard';
import { StaggerItem, StaggerList } from '@/components/ui/motion';
import { useMigrations } from '@/hooks/useMigration';
import { isActive } from '@/lib/utils';
import { brand } from '@/theme';

const { Text, Title } = Typography;

export function Dashboard() {
  const navigate = useNavigate();
  const { data: jobs, isLoading } = useMigrations();

  const running = jobs?.filter((j) => isActive(j.status)).length ?? 0;
  const completed = jobs?.filter((j) => j.status === 'completed').length ?? 0;
  const totalRows = jobs?.reduce((acc, j) => acc + j.rows_migrated, 0) ?? 0;

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }} align="center">
        <div>
          <Title level={3} style={{ margin: 0, letterSpacing: '-0.02em' }}>
            Migrations
          </Title>
          <Text type="secondary" style={{ fontSize: 13.5 }}>
            Every migration job, live.
          </Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/migrations/new')}>
          New migration
        </Button>
      </Space>

      <Row gutter={[16, 16]}>
        {[
          { title: 'Active now', value: running },
          { title: 'Completed', value: completed },
          { title: 'Rows migrated', value: totalRows },
        ].map((s) => (
          <Col xs={24} sm={8} key={s.title}>
            <Card
              variant="outlined"
              className="glass-panel"
              style={{ borderRadius: 14 }}
              styles={{ body: { padding: 18 } }}
            >
              <Statistic
                title={<Text style={{ fontSize: 12.5, color: brand.inkMuted }}>{s.title}</Text>}
                value={s.value}
                valueStyle={{ fontSize: 26, fontWeight: 650, color: brand.ink, fontFamily: "'Satoshi', sans-serif" }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {isLoading ? (
        <Row gutter={[16, 16]}>
          {[1, 2, 3].map((k) => (
            <Col xs={24} md={12} xl={8} key={k}>
              <Card variant="outlined" className="glass-panel" style={{ borderRadius: 14 }}>
                <Skeleton active paragraph={{ rows: 3 }} />
              </Card>
            </Col>
          ))}
        </Row>
      ) : jobs && jobs.length > 0 ? (
        <StaggerList>
          <Row gutter={[16, 16]}>
            {jobs.map((job) => (
              <Col xs={24} md={12} xl={8} key={job.id}>
                <StaggerItem>
                  <MigrationCard job={job} />
                </StaggerItem>
              </Col>
            ))}
          </Row>
        </StaggerList>
      ) : (
        <Card variant="outlined" className="glass-panel" style={{ borderRadius: 14 }}>
          <Empty description="No migrations yet">
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/migrations/new')}>
              Start your first migration
            </Button>
          </Empty>
        </Card>
      )}
    </Space>
  );
}

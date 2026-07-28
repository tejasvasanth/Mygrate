import { Card, Col, List, Row, Skeleton, Space, Tag, Typography } from 'antd';
import { BulbOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { DbPair } from '@/components/migration/DbBadge';
import { useTemplates } from '@/hooks/useMigration';
import { brand } from '@/theme';

const { Text, Title, Paragraph } = Typography;

/**
 * T3-4 — public template library. Each card documents the type quirks that
 * actually bite when migrating that stack, which is both useful and the SEO
 * surface for the product.
 */
export function Templates() {
  const { data: templates, isLoading } = useTemplates();

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <div>
        <Title level={3} style={{ margin: 0, letterSpacing: '-0.02em' }}>
          Migration templates
        </Title>
        <Text type="secondary" style={{ fontSize: 13.5 }}>
          Known type quirks for common stacks, pre-loaded so Migrate does not have to
          rediscover them.
        </Text>
      </div>

      {isLoading ? (
        <Card variant="outlined" className="glass-panel" style={{ borderRadius: 14 }}>
          <Skeleton active paragraph={{ rows: 6 }} />
        </Card>
      ) : null}

      <Row gutter={[16, 16]}>
        {(templates ?? []).map((t) => (
          <Col xs={24} lg={12} key={t.slug}>
            <Card
              variant="outlined"
              className="glass-panel"
              style={{ borderRadius: 14, height: '100%' }}
              styles={{ body: { padding: 22 } }}
              title={
                <Space direction="vertical" size={6} style={{ paddingTop: 8 }}>
                  <Space>
                    <ThunderboltOutlined style={{ color: brand.green600 }} />
                    <Text strong>{t.title}</Text>
                  </Space>
                  <DbPair source={t.source_db_type} target={t.target_db_type} />
                </Space>
              }
              extra={<Tag>{t.stack}</Tag>}
            >
              <Paragraph style={{ fontSize: 13 }}>{t.summary}</Paragraph>
              <Space size={6} align="center" style={{ marginBottom: 6 }}>
                <BulbOutlined style={{ color: '#F59E0B' }} />
                <Text strong style={{ fontSize: 13 }}>
                  What breaks if you migrate this naively
                </Text>
              </Space>
              <List
                size="small"
                dataSource={t.quirks}
                renderItem={(q) => (
                  <List.Item style={{ paddingLeft: 0, border: 'none', paddingBlock: 3 }}>
                    <Text style={{ fontSize: 12.5 }}>• {q}</Text>
                  </List.Item>
                )}
              />
            </Card>
          </Col>
        ))}
      </Row>
    </Space>
  );
}

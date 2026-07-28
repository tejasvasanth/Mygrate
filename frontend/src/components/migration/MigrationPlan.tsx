import { Alert, Card, Collapse, Space, Table, Tag, Typography } from 'antd';
import { WarningOutlined } from '@ant-design/icons';
import { brand } from '@/theme';
import { formatFullNumber } from '@/lib/utils';
import type { ColumnMapping, MigrationPlanData } from '@/types';

const { Paragraph, Text, Title } = Typography;

/**
 * Renders the AI-generated plan for review before execution.
 * Dry run is never skipped (god.md §14) — this is what the user approves.
 */
export function MigrationPlan({ plan }: { plan: MigrationPlanData }) {
  const columns = [
    {
      title: 'Source column',
      dataIndex: 'source_column',
      key: 'source_column',
      render: (value: string) => <Text code>{value}</Text>,
    },
    {
      title: 'Target column',
      dataIndex: 'target_column',
      key: 'target_column',
      render: (value: string) => <Text code>{value}</Text>,
    },
    {
      title: 'Type',
      key: 'type',
      render: (_: unknown, row: ColumnMapping) => (
        <Space size={6}>
          <Text type="secondary" style={{ fontSize: 12.5 }}>
            {row.source_type}
          </Text>
          <Text type="secondary" style={{ fontSize: 11 }}>
            →
          </Text>
          <Text style={{ fontSize: 12.5, color: brand.green700, fontWeight: 500 }}>
            {row.target_type}
          </Text>
        </Space>
      ),
    },
    {
      title: 'Coercion',
      key: 'coercion',
      render: (_: unknown, row: ColumnMapping) => {
        const value = row.transformation ?? row.coercion;
        return value ? (
          <Tag color="success" style={{ borderRadius: 6, whiteSpace: 'normal' }}>
            {value}
          </Tag>
        ) : (
          <Text type="secondary" style={{ fontSize: 12.5 }}>
            Direct
          </Text>
        );
      },
    },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card
        variant="outlined"
        style={{ borderRadius: 14, background: brand.green50, borderColor: brand.green200 }}
        styles={{ body: { padding: 20 } }}
      >
        <Title level={5} style={{ marginTop: 0, marginBottom: 8, fontSize: 14 }}>
          Plan summary
        </Title>
        <Paragraph style={{ margin: 0, fontSize: 13.5, color: brand.inkSoft }}>
          {plan.summary}
        </Paragraph>
      </Card>

      {plan.global_warnings.length > 0 ? (
        <Alert
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          message="Review before approving"
          description={
            <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
              {plan.global_warnings.map((warning) => (
                <li key={warning} style={{ fontSize: 13 }}>
                  {warning}
                </li>
              ))}
            </ul>
          }
        />
      ) : null}

      <Collapse
        accordion
        defaultActiveKey={plan.tables[0]?.source_table}
        style={{ background: 'transparent', borderRadius: 14 }}
        items={plan.tables.map((table) => ({
          key: table.source_table,
          label: (
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Space size={8}>
                <Text strong style={{ fontSize: 13.5 }}>
                  {table.source_table}
                </Text>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  →
                </Text>
                <Text style={{ fontSize: 13.5, color: brand.green700 }}>
                  {table.target_table_name}
                </Text>
              </Space>
              <Space size={8}>
                {table.warnings.length > 0 ? (
                  <Tag color="warning" style={{ borderRadius: 99, margin: 0 }}>
                    {table.warnings.length} warning{table.warnings.length > 1 ? 's' : ''}
                  </Tag>
                ) : null}
                <Text type="secondary" style={{ fontSize: 12 }}>
                  ~{formatFullNumber(table.estimated_rows)} rows
                </Text>
              </Space>
            </Space>
          ),
          children: (
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Table<ColumnMapping>
                size="small"
                pagination={false}
                rowKey={(row) => row.source_column}
                columns={columns}
                dataSource={table.column_mappings}
              />

              <div>
                <Text strong style={{ fontSize: 13 }}>
                  Relationship handling
                </Text>
                <Paragraph style={{ margin: '4px 0 0', fontSize: 13, color: brand.inkSoft }}>
                  {table.relationship_handling}
                </Paragraph>
              </div>

              {table.transformation_rules.length > 0 ? (
                <div>
                  <Text strong style={{ fontSize: 13 }}>
                    Transformation rules
                  </Text>
                  <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
                    {table.transformation_rules.map((rule) => (
                      <li key={rule} style={{ fontSize: 13, color: brand.inkSoft }}>
                        {rule}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {table.warnings.length > 0 ? (
                <Alert
                  type="warning"
                  showIcon
                  message={
                    <ul style={{ margin: 0, paddingLeft: 18 }}>
                      {table.warnings.map((warning) => (
                        <li key={warning} style={{ fontSize: 13 }}>
                          {warning}
                        </li>
                      ))}
                    </ul>
                  }
                />
              ) : null}
            </Space>
          ),
        }))}
      />
    </Space>
  );
}

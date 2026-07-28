import { useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Empty,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import { ExperimentOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { brand } from '@/theme';
import type { SimulationCell, SimulationResult, SimulationRow } from '@/types';

const { Text } = Typography;

const CHANGED_BG = 'rgba(245, 158, 11, 0.14)';

function renderCell(value: SimulationCell) {
  if (value === null) return <Text type="secondary">NULL</Text>;
  if (typeof value === 'boolean') {
    return <Tag color={value ? 'green' : 'default'}>{String(value)}</Tag>;
  }
  return <Text style={{ fontSize: 12.5 }}>{String(value)}</Text>;
}

/**
 * T2-1 — before/after preview of the plan applied to real sampled rows.
 * Cells the coercion changed are highlighted, so "TINYINT 1 → true" is
 * visible rather than implied.
 */
export function SimulationView({
  simulation,
  onRun,
  running,
}: {
  simulation?: SimulationResult;
  onRun?: () => void;
  running?: boolean;
}) {
  const tableNames = Object.keys(simulation?.tables ?? {});
  const [selected, setSelected] = useState<string | undefined>(tableNames[0]);
  const active = selected ?? tableNames[0];
  const table = active ? simulation?.tables[active] : undefined;

  return (
    <Card
      variant="outlined"
      className="glass-panel"
      style={{ borderRadius: 14 }}
      styles={{ body: { padding: 22 } }}
      title={
        <Space>
          <ExperimentOutlined style={{ color: brand.green600 }} />
          <Text strong>Migration simulation</Text>
          {simulation ? (
            <Tag color={simulation.total_rows_with_changes > 0 ? 'orange' : 'green'}>
              {simulation.total_rows_with_changes} of {simulation.total_rows_simulated}{' '}
              sampled rows change
            </Tag>
          ) : null}
        </Space>
      }
      extra={
        onRun ? (
          <Button
            size="small"
            icon={<PlayCircleOutlined />}
            loading={running}
            onClick={onRun}
          >
            {simulation ? 'Re-run simulation' : 'Run simulation'}
          </Button>
        ) : null
      }
    >
      {!simulation ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <Space direction="vertical" size={4}>
              <Text>No simulation has been run yet.</Text>
              <Text type="secondary" style={{ fontSize: 12.5 }}>
                A simulation applies the plan's type coercions to sampled rows so you
                can see exactly what changes — nothing is written to the target.
              </Text>
            </Space>
          }
        />
      ) : (
        <Space direction="vertical" size={14} style={{ width: '100%' }}>
          <Alert
            type="info"
            showIcon
            message="This is a dry run against sampled rows"
            description="The target database has not been touched. Highlighted cells are values the migration plan would change."
          />

          {tableNames.length > 1 ? (
            <Select
              value={active}
              onChange={setSelected}
              style={{ minWidth: 240 }}
              options={tableNames.map((name) => ({
                value: name,
                label: `${name} → ${simulation.tables[name].target_table}`,
              }))}
            />
          ) : null}

          {table ? (
            <>
              <Text type="secondary" style={{ fontSize: 12.5 }}>
                {table.rows_with_changes} of {table.rows_simulated} sampled rows are
                changed by the plan. Showing the first {table.rows.length}.
              </Text>
              <Table<SimulationRow>
                size="small"
                rowKey={(_row, index) => String(index)}
                dataSource={table.rows}
                pagination={table.rows.length > 10 ? { pageSize: 10 } : false}
                scroll={{ x: 'max-content' }}
                columns={[
                  {
                    title: 'Source row (as it is today)',
                    key: 'source',
                    children: table.columns.map((c) => ({
                      title: (
                        <Space direction="vertical" size={0}>
                          <Text style={{ fontSize: 12 }}>{c.source}</Text>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {c.source_type}
                          </Text>
                        </Space>
                      ),
                      key: `s-${c.source}`,
                      render: (_: unknown, row: SimulationRow) =>
                        renderCell(row.source[c.source]),
                    })),
                  },
                  {
                    title: 'After migration',
                    key: 'transformed',
                    children: table.columns.map((c) => ({
                      title: (
                        <Space direction="vertical" size={0}>
                          <Text style={{ fontSize: 12 }}>{c.target}</Text>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {c.target_type}
                          </Text>
                        </Space>
                      ),
                      key: `t-${c.target}`,
                      onCell: (row: SimulationRow) =>
                        row.changed_columns.includes(c.target)
                          ? { style: { background: CHANGED_BG } }
                          : {},
                      render: (_: unknown, row: SimulationRow) =>
                        renderCell(row.transformed[c.target]),
                    })),
                  },
                ]}
              />
            </>
          ) : null}
        </Space>
      )}
    </Card>
  );
}

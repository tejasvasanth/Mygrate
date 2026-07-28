import { useState } from 'react';
import {
  App as AntApp,
  Alert,
  Button,
  Card,
  Empty,
  Input,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
} from 'antd';
import type { UploadFile as AntUploadFile } from 'antd';
import {
  CheckCircleOutlined,
  FileExcelOutlined,
  InboxOutlined,
  RobotOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useMutation } from '@tanstack/react-query';
import { api, apiErrorMessage } from '@/lib/api';
import { DB_LABELS } from '@/lib/utils';
import { useSavedConnections } from '@/hooks/useMigration';
import { brand } from '@/theme';
import { DB_TYPES, type DbType } from '@/types';

const { Text, Title, Paragraph } = Typography;

interface ColumnMapping {
  source: string;
  target: string;
  transform: string | null;
}

interface OperationPlan {
  kind: 'insert' | 'create_and_insert' | 'unsupported';
  target_table?: string;
  new_table_columns?: Array<{ name: string; canonical_type: string; ddl_type?: string }>;
  column_mapping: ColumnMapping[];
  inline_rows: Array<Record<string, unknown>>;
  summary: string;
  warnings: string[];
  ai_generated: boolean;
  row_count: number;
}

interface PreviewResponse {
  plan: OperationPlan;
  file_headers: string[];
  file_row_count: number;
  sample_rows: Array<Record<string, unknown>>;
  known_tables: string[];
}

interface ExecuteResponse {
  ok: boolean;
  table: string;
  rows_written: number;
  created_table: boolean;
}

export function Operations() {
  const { message } = AntApp.useApp();
  const { data: connections, isLoading: connectionsLoading } = useSavedConnections();

  const [connectionMode, setConnectionMode] = useState<'saved' | 'manual'>('saved');
  const [connectionId, setConnectionId] = useState<string>();
  const [dbType, setDbType] = useState<DbType>('postgres');
  const [connectionString, setConnectionString] = useState('');
  const [instruction, setInstruction] = useState('');
  const [fileList, setFileList] = useState<AntUploadFile[]>([]);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [result, setResult] = useState<ExecuteResponse | null>(null);

  const connectionReady =
    connectionMode === 'saved' ? Boolean(connectionId) : connectionString.trim().length > 0;

  const buildForm = () => {
    const form = new FormData();
    if (connectionMode === 'saved') {
      form.append('connection_id', connectionId ?? '');
    } else {
      form.append('db_type', dbType);
      form.append('connection_string', connectionString);
    }
    const raw = fileList[0]?.originFileObj;
    if (raw) form.append('file', raw);
    return form;
  };

  const previewMutation = useMutation({
    mutationFn: async () => {
      const form = buildForm();
      form.append('instruction', instruction);
      return (
        await api.post<PreviewResponse>('/operations/preview', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 120_000,
        })
      ).data;
    },
    onSuccess: (data) => {
      setPreview(data);
      setResult(null);
    },
    onError: (e) => message.error(apiErrorMessage(e)),
  });

  const executeMutation = useMutation({
    mutationFn: async () => {
      if (!preview) throw new Error('Preview the operation first');
      const form = buildForm();
      form.append('plan_json', JSON.stringify(preview.plan));
      return (
        await api.post<ExecuteResponse>('/operations/execute', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 300_000,
        })
      ).data;
    },
    onSuccess: (data) => {
      setResult(data);
      setPreview(null);
      message.success(`${data.rows_written} rows written to '${data.table}'`);
    },
    onError: (e) => message.error(apiErrorMessage(e)),
  });

  const plan = preview?.plan;
  const executable = plan && plan.kind !== 'unsupported';

  return (
    <Space direction="vertical" size={20} style={{ width: '100%' }}>
      <div>
        <Title level={3} style={{ margin: 0, letterSpacing: '-0.02em' }}>
          Operations
        </Title>
        <Text type="secondary" style={{ fontSize: 13.5 }}>
          Tell the agent what to do — or drop a spreadsheet — and review its plan before
          anything touches your database.
        </Text>
      </div>

      <Card variant="outlined" className="glass-panel" style={{ borderRadius: 14 }} styles={{ body: { padding: 24 } }}>
        <Space direction="vertical" size={18} style={{ width: '100%' }}>
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
              Database
            </Text>
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <Segmented
                value={connectionMode}
                onChange={(v) => {
                  setConnectionMode(v as 'saved' | 'manual');
                  setPreview(null);
                  setResult(null);
                }}
                options={[
                  { label: 'Saved connection', value: 'saved' },
                  { label: 'Type a connection string', value: 'manual' },
                ]}
              />
              {connectionMode === 'saved' ? (
                <Select
                  style={{ width: '100%', maxWidth: 480 }}
                  placeholder={
                    connectionsLoading ? 'Loading connections…' : 'Select a saved connection'
                  }
                  value={connectionId}
                  onChange={setConnectionId}
                  options={(connections ?? []).map((c) => ({
                    value: c.id,
                    label: `${c.nickname} — ${DB_LABELS[c.db_type] ?? c.db_type}`,
                  }))}
                  notFoundContent={
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description="No saved connections — save one on the Connections page first"
                    />
                  }
                />
              ) : (
                <Space.Compact style={{ width: '100%', maxWidth: 640 }}>
                  <Select
                    style={{ width: 240 }}
                    showSearch
                    optionFilterProp="label"
                    value={dbType}
                    onChange={setDbType}
                    options={DB_TYPES.map((t) => ({ value: t, label: DB_LABELS[t] }))}
                  />
                  <Input.Password
                    style={{ flex: 1 }}
                    placeholder="postgresql://user:password@host:5432/database"
                    value={connectionString}
                    onChange={(e) => setConnectionString(e.target.value)}
                    autoComplete="off"
                  />
                </Space.Compact>
              )}
              {connectionMode === 'manual' ? (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Used in-memory for this operation only — never stored.
                </Text>
              ) : null}
            </Space>
          </div>

          <div>
            <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
              Instruction
            </Text>
            <Input.TextArea
              rows={3}
              placeholder='e.g. "Add these customers to the users table" or "Add a row to products: name=Desk Lamp, price=39.99"'
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
            />
          </div>

          <div>
            <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
              Spreadsheet (optional)
            </Text>
            <Upload.Dragger
              accept=".xlsx,.csv,.tsv"
              maxCount={1}
              fileList={fileList}
              beforeUpload={() => false}
              onChange={({ fileList: fl }) => {
                setFileList(fl);
                setPreview(null);
                setResult(null);
              }}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined style={{ color: brand.green600 }} />
              </p>
              <p style={{ fontSize: 13.5 }}>Click or drag an .xlsx / .csv file here</p>
              <p style={{ fontSize: 12, color: brand.inkMuted }}>
                First row must be column headers · max 20 MB
              </p>
            </Upload.Dragger>
          </div>

          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={previewMutation.isPending}
            disabled={!connectionReady || (!instruction.trim() && fileList.length === 0)}
            onClick={() => previewMutation.mutate()}
          >
            Preview plan
          </Button>
        </Space>
      </Card>

      {plan ? (
        <Card
          variant="outlined"
          className="glass-panel"
          style={{ borderRadius: 14 }}
          styles={{ body: { padding: 22 } }}
          title={
            <Space>
              <Text strong>Proposed operation</Text>
              {plan.ai_generated ? (
                <Tag icon={<RobotOutlined />} color="green">
                  AI-planned
                </Tag>
              ) : (
                <Tag>Rule-based</Tag>
              )}
              {plan.kind === 'create_and_insert' ? (
                <Tag color="blue">Creates new table</Tag>
              ) : null}
            </Space>
          }
          extra={
            executable ? (
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                loading={executeMutation.isPending}
                onClick={() => executeMutation.mutate()}
              >
                Approve & execute
              </Button>
            ) : null
          }
        >
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Paragraph style={{ margin: 0, fontSize: 13.5 }}>{plan.summary}</Paragraph>

            {plan.warnings.map((w) => (
              <Alert key={w} type="warning" showIcon message={w} />
            ))}

            {plan.kind === 'unsupported' ? (
              <Alert
                type="error"
                showIcon
                message="This operation cannot be executed"
                description="v1 supports inserting rows and creating tables. Updates and deletes are coming later."
              />
            ) : null}

            {plan.column_mapping.length > 0 ? (
              <div>
                <Space size={6} style={{ marginBottom: 8 }}>
                  <FileExcelOutlined />
                  <Text strong style={{ fontSize: 13 }}>
                    Column mapping → {plan.target_table}
                  </Text>
                </Space>
                <Table
                  size="small"
                  rowKey={(m) => m.source}
                  pagination={false}
                  dataSource={plan.column_mapping}
                  columns={[
                    { title: 'File column', dataIndex: 'source' },
                    { title: 'Database column', dataIndex: 'target' },
                    {
                      title: 'Transform',
                      dataIndex: 'transform',
                      render: (t: string | null) => t ?? '—',
                    },
                  ]}
                />
              </div>
            ) : null}

            {preview && preview.sample_rows.length > 0 ? (
              <div>
                <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
                  Data preview ({preview.file_row_count} rows total)
                </Text>
                <Table
                  size="small"
                  rowKey={(_, i) => String(i)}
                  pagination={false}
                  scroll={{ x: true }}
                  dataSource={preview.sample_rows}
                  columns={preview.file_headers.map((h) => ({
                    title: h,
                    dataIndex: h,
                    render: (v: unknown) => String(v ?? ''),
                  }))}
                />
              </div>
            ) : null}

            {plan.inline_rows.length > 0 ? (
              <div>
                <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
                  Rows extracted from your instruction
                </Text>
                <Table
                  size="small"
                  rowKey={(_, i) => String(i)}
                  pagination={false}
                  scroll={{ x: true }}
                  dataSource={plan.inline_rows}
                  columns={Object.keys(plan.inline_rows[0] ?? {}).map((h) => ({
                    title: h,
                    dataIndex: h,
                    render: (v: unknown) => String(v ?? ''),
                  }))}
                />
              </div>
            ) : null}
          </Space>
        </Card>
      ) : null}

      {result ? (
        <Alert
          type="success"
          showIcon
          message={`Done — ${result.rows_written} rows written to '${result.table}'`}
          description={
            result.created_table ? `A new table '${result.table}' was created.` : undefined
          }
        />
      ) : null}
    </Space>
  );
}

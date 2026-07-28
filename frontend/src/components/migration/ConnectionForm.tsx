import { useEffect } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AnimatePresence, motion } from 'framer-motion';
import { Alert, Button, Card, Input, Select, Space, Tag, Typography } from 'antd';
import {
  CheckCircleFilled,
  LinkOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useSavedConnections, useTestConnection } from '@/hooks/useMigration';
import { apiErrorMessage } from '@/lib/api';
import { DB_LABELS } from '@/lib/utils';
import { brand } from '@/theme';
import type { ConnectionDraft } from '@/store/migrationStore';
import { DB_FAMILY, DB_TYPES, type DbFamily, type DbType } from '@/types';

const { Text, Title } = Typography;

const schema = z.object({
  db_type: z.enum(DB_TYPES),
  connection_string: z.string().min(1, 'Connection string is required'),
});

type FormValues = z.infer<typeof schema>;

/** Placeholder per engine family so users see the expected shape. */
const PLACEHOLDERS: Record<DbFamily, string> = {
  postgres: 'postgresql://user:password@host:5432/database',
  mysql: 'mysql://user:password@host:3306/database',
  mongodb: 'mongodb+srv://user:password@cluster.mongodb.net/database',
  sqlite: 'sqlite:///absolute/path/to/database.db',
  sqlserver: 'mssql://user:password@host:1433/database',
  bigquery: 'bigquery://project-id/dataset?credentials_path=C:/keys/sa.json',
  dynamodb: 'dynamodb://ACCESS_KEY:SECRET_KEY@us-east-1',
  neo4j: 'neo4j://user:password@host:7687',
};

interface Props {
  title: string;
  description: string;
  value: ConnectionDraft;
  onChange: (patch: Partial<ConnectionDraft>) => void;
}

export function ConnectionForm({ title, description, value, onChange }: Props) {
  const testConnection = useTestConnection();
  const { data: savedConnections } = useSavedConnections();

  const { control, handleSubmit, watch, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      db_type: value.db_type,
      connection_string: value.connection_string,
    },
    mode: 'onChange',
  });

  const dbType = watch('db_type');
  const connectionString = watch('connection_string');

  // Mirror form edits into the wizard store so navigating between steps
  // preserves what was typed.
  useEffect(() => {
    if (dbType !== value.db_type) onChange({ db_type: dbType });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dbType]);

  useEffect(() => {
    if (connectionString !== value.connection_string) {
      onChange({ connection_string: connectionString });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionString]);

  const onTest = handleSubmit((values) => {
    testConnection.mutate(values, {
      onSuccess: (result) => {
        onChange({
          tested: result.ok,
          discovered_tables: result.tables ?? [],
        });
      },
    });
  });

  const result = testConnection.data;

  return (
    <Card variant="outlined" className="glass-panel" style={{ borderRadius: 14 }} styles={{ body: { padding: 24 } }}>
      <Space direction="vertical" size={20} style={{ width: '100%' }}>
        <div>
          <Title level={4} style={{ margin: 0, fontSize: 17 }}>
            {title}
          </Title>
          <Text type="secondary" style={{ fontSize: 13.5 }}>
            {description}
          </Text>
        </div>

        {savedConnections && savedConnections.length > 0 ? (
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
              Use a saved connection
            </Text>
            <Select
              allowClear
              style={{ width: '100%' }}
              placeholder="Choose a saved connection, or enter one below"
              value={value.connection_id ?? undefined}
              onChange={(id?: string) => {
                const saved = savedConnections.find((c) => c.id === id);
                if (!saved) {
                  // Cleared — fall back to manual entry.
                  onChange({ connection_id: null, tested: false });
                  return;
                }
                // The credential stays in Vault; we only carry its id. Mark
                // as tested since it was verified when it was saved.
                onChange({
                  connection_id: saved.id,
                  db_type: saved.db_type,
                  connection_string: '',
                  tested: true,
                  discovered_tables: [],
                });
              }}
              options={savedConnections.map((c) => ({
                value: c.id,
                label: `${c.nickname} · ${DB_LABELS[c.db_type]}${
                  c.host ? ` · ${c.host}` : ''
                }`,
              }))}
            />
          </div>
        ) : null}

        {value.connection_id ? (
          <Alert
            type="success"
            showIcon
            message="Using a saved connection"
            description="Its credential is read from Supabase Vault when the migration runs — it never enters the browser. Clear the selection above to enter a different connection."
          />
        ) : null}

        <div style={value.connection_id ? { opacity: 0.45, pointerEvents: 'none' } : undefined}>
          <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
            Database engine
          </Text>
          <Controller
            name="db_type"
            control={control}
            render={({ field }) => (
              <Select
                {...field}
                style={{ width: '100%' }}
                showSearch
                optionFilterProp="label"
                options={DB_TYPES.map((type: DbType) => ({
                  value: type,
                  label: DB_LABELS[type],
                }))}
              />
            )}
          />
        </div>

        <div style={value.connection_id ? { opacity: 0.45, pointerEvents: 'none' } : undefined}>
          <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
            Connection string
          </Text>
          <Controller
            name="connection_string"
            control={control}
            render={({ field, fieldState }) => (
              <>
                <Input.Password
                  {...field}
                  prefix={<LinkOutlined style={{ color: brand.inkMuted }} />}
                  placeholder={PLACEHOLDERS[DB_FAMILY[dbType]]}
                  status={fieldState.error ? 'error' : undefined}
                  autoComplete="off"
                />
                {fieldState.error ? (
                  <Text type="danger" style={{ fontSize: 12.5 }}>
                    {fieldState.error.message}
                  </Text>
                ) : null}
              </>
            )}
          />

          <Space size={6} style={{ marginTop: 10 }}>
            <SafetyCertificateOutlined style={{ color: brand.green600, fontSize: 13 }} />
            <Text type="secondary" style={{ fontSize: 12.2 }}>
              Testing never stores your credential. Saved connections go straight to Supabase
              Vault — we only keep the vault ID.
            </Text>
          </Space>
        </div>

        <Space>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={testConnection.isPending}
            disabled={!formState.isValid}
            onClick={() => void onTest()}
          >
            Test connection
          </Button>
          {value.tested ? (
            <Tag
              icon={<CheckCircleFilled />}
              color="success"
              style={{ borderRadius: 99, margin: 0 }}
            >
              Verified
            </Tag>
          ) : null}
        </Space>

        {/* Result panel slides open rather than appearing abruptly. */}
        <AnimatePresence mode="wait">
          {testConnection.isError ? (
            <motion.div
              key="error"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            >
              <Alert
                type="error"
                showIcon
                message="Could not connect"
                description={apiErrorMessage(testConnection.error)}
              />
            </motion.div>
          ) : result ? (
            <motion.div
              key="result"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            >
              <Alert
                type={result.ok ? 'success' : 'error'}
                showIcon
                message={result.ok ? 'Connection successful' : 'Connection failed'}
                description={
                  <Space direction="vertical" size={4}>
                    <Text style={{ fontSize: 13 }}>{result.message}</Text>
                    {result.server_version ? (
                      <Text type="secondary" style={{ fontSize: 12.5 }}>
                        Server {result.server_version}
                        {result.latency_ms ? ` · ${result.latency_ms}ms` : ''}
                      </Text>
                    ) : null}
                    {result.tables?.length ? (
                      <Text type="secondary" style={{ fontSize: 12.5 }}>
                        {result.tables.length} tables discovered
                      </Text>
                    ) : null}
                  </Space>
                }
              />
              {result.ok && result.readonly_advice ? (
                <Alert
                  type="warning"
                  showIcon
                  style={{ marginTop: 12 }}
                  message="This connection can write to your database"
                  description={
                    <Space direction="vertical" size={8} style={{ marginTop: 4 }}>
                      <Text style={{ fontSize: 13 }}>
                        {result.readonly_advice.warning}
                      </Text>
                      <Text strong style={{ fontSize: 12.5 }}>
                        Create a read-only user instead:
                      </Text>
                      <Input.TextArea
                        readOnly
                        rows={Math.min(6, result.readonly_advice.grant_sql.length)}
                        value={result.readonly_advice.grant_sql.join('\n')}
                        style={{ fontFamily: 'monospace', fontSize: 12 }}
                      />
                      <Text strong style={{ fontSize: 12.5 }}>
                        Then connect with:
                      </Text>
                      <Input
                        readOnly
                        value={result.readonly_advice.connection_string}
                        style={{ fontFamily: 'monospace', fontSize: 12 }}
                      />
                    </Space>
                  }
                />
              ) : null}
              {result.ok && result.has_write_access === false ? (
                <Alert
                  type="success"
                  showIcon
                  style={{ marginTop: 12 }}
                  message="Read-only connection"
                  description={
                    result.privilege_evidence ??
                    'This credential cannot modify your source database.'
                  }
                />
              ) : null}
            </motion.div>
          ) : null}
        </AnimatePresence>
      </Space>
    </Card>
  );
}

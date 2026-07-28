import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  App as AntApp,
  Alert,
  Button,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Typography,
} from 'antd';
import { CheckCircleOutlined, LockOutlined } from '@ant-design/icons';
import { useSaveConnection, useTestConnection } from '@/hooks/useMigration';
import { apiErrorMessage } from '@/lib/api';
import { DB_LABELS } from '@/lib/utils';
import { DB_FAMILY, DB_TYPES, type DbFamily, type DbType } from '@/types';

const { Text } = Typography;

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

const schema = z.object({
  nickname: z.string().min(1, 'Give this connection a name').max(100),
  db_type: z.string().min(1),
  connection_string: z.string().min(1, 'A connection string is required'),
});

type FormValues = z.infer<typeof schema>;

/**
 * Parse host/port/database out of the URL purely for display in the list.
 * The connection string itself is never stored — only its Vault id is.
 */
function parseMetadata(connectionString: string): {
  host: string | null;
  port: number | null;
  database_name: string | null;
} {
  try {
    const url = new URL(connectionString);
    const database = url.pathname.replace(/^\//, '').split('?')[0];
    return {
      host: url.hostname || null,
      port: url.port ? Number(url.port) : null,
      database_name: database || null,
    };
  } catch {
    // SQLite paths and other non-URL strings — nothing to show, which is fine.
    return { host: null, port: null, database_name: null };
  }
}

export function SaveConnectionModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { message } = AntApp.useApp();
  const testConnection = useTestConnection();
  const saveConnection = useSaveConnection();
  const [tested, setTested] = useState<{ ok: boolean; detail: string } | null>(null);

  const { control, handleSubmit, watch, reset, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { nickname: '', db_type: 'postgres', connection_string: '' },
  });

  const dbType = watch('db_type') as DbType;
  const connectionString = watch('connection_string');

  const close = () => {
    reset();
    setTested(null);
    onClose();
  };

  const runTest = () => {
    if (!connectionString) {
      message.warning('Enter a connection string first.');
      return;
    }
    testConnection.mutate(
      { db_type: dbType, connection_string: connectionString },
      {
        onSuccess: (result) =>
          setTested({
            ok: result.ok,
            detail: result.ok
              ? `${result.tables?.length ?? 0} tables discovered.${
                  result.has_write_access
                    ? ' This credential can write — a read-only one is safer.'
                    : ''
                }`
              : result.message,
          }),
        onError: (e) => setTested({ ok: false, detail: apiErrorMessage(e) }),
      },
    );
  };

  const onSubmit = (values: FormValues) => {
    saveConnection.mutate(
      {
        nickname: values.nickname,
        db_type: values.db_type as DbType,
        connection_string: values.connection_string,
        ...parseMetadata(values.connection_string),
      },
      {
        onSuccess: () => {
          message.success('Connection saved — the credential is in Vault.');
          close();
        },
        onError: (e) => message.error(apiErrorMessage(e)),
      },
    );
  };

  return (
    <Modal
      open={open}
      onCancel={close}
      title="Save a connection"
      okText="Save connection"
      confirmLoading={saveConnection.isPending}
      onOk={handleSubmit(onSubmit)}
      destroyOnHidden
      width={620}
    >
      <Space direction="vertical" size={14} style={{ width: '100%', marginTop: 8 }}>
        <Alert
          type="info"
          showIcon
          icon={<LockOutlined />}
          message="Your credential goes straight to Supabase Vault"
          description="Only the nickname, engine and host are stored in our database. The connection string is never written to logs, disk, or returned to the browser."
        />

        <Form layout="vertical" style={{ marginBottom: 0 }}>
          <Controller
            name="nickname"
            control={control}
            render={({ field, fieldState }) => (
              <Form.Item
                label="Nickname"
                required
                validateStatus={fieldState.error ? 'error' : undefined}
                help={fieldState.error?.message}
              >
                <Input {...field} placeholder="Production Postgres" />
              </Form.Item>
            )}
          />

          <Controller
            name="db_type"
            control={control}
            render={({ field }) => (
              <Form.Item label="Engine" required>
                <Select
                  {...field}
                  showSearch
                  optionFilterProp="label"
                  onChange={(v) => {
                    field.onChange(v);
                    setTested(null);
                  }}
                  options={DB_TYPES.map((t) => ({ value: t, label: DB_LABELS[t] }))}
                />
              </Form.Item>
            )}
          />

          <Controller
            name="connection_string"
            control={control}
            render={({ field, fieldState }) => (
              <Form.Item
                label="Connection string"
                required
                validateStatus={fieldState.error ? 'error' : undefined}
                help={fieldState.error?.message}
              >
                <Input.Password
                  {...field}
                  onChange={(e) => {
                    field.onChange(e);
                    setTested(null);
                  }}
                  placeholder={PLACEHOLDERS[DB_FAMILY[dbType]]}
                  autoComplete="off"
                />
              </Form.Item>
            )}
          />
        </Form>

        <Space>
          <Button
            onClick={runTest}
            loading={testConnection.isPending}
            icon={<CheckCircleOutlined />}
          >
            Test connection
          </Button>
          <Text type="secondary" style={{ fontSize: 12.5 }}>
            Optional, but worth doing before saving.
          </Text>
        </Space>

        {tested ? (
          <Alert
            type={tested.ok ? 'success' : 'error'}
            showIcon
            message={tested.ok ? 'Connection successful' : 'Connection failed'}
            description={tested.detail}
          />
        ) : null}

        {formState.errors.db_type ? (
          <Text type="danger">{formState.errors.db_type.message}</Text>
        ) : null}
      </Space>
    </Modal>
  );
}

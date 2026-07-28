import { useNavigate } from 'react-router-dom';
import {
  App as AntApp,
  Button,
  Card,
  Col,
  Input,
  InputNumber,
  Row,
  Segmented,
  Select,
  Space,
  Steps,
  Switch,
  Typography,
} from 'antd';
import { ArrowLeftOutlined, ArrowRightOutlined, RocketOutlined } from '@ant-design/icons';
import { ConnectionForm } from '@/components/migration/ConnectionForm';
import { DbPair } from '@/components/migration/DbBadge';
import { useCreateMigration, useStartMigration } from '@/hooks/useMigration';
import { apiErrorMessage } from '@/lib/api';
import { pairDifficulty } from '@/lib/utils';
import { useMigrationStore } from '@/store/migrationStore';
import { brand } from '@/theme';
import type { ConflictStrategy } from '@/types';

const { Text, Title } = Typography;

export function NewMigration() {
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const store = useMigrationStore();
  const createMigration = useCreateMigration();
  const startMigration = useStartMigration();

  const canLeaveStep =
    store.step === 0 ? store.source.tested : store.step === 1 ? store.target.tested : true;

  const submit = () => {
    createMigration.mutate(
      {
        name: store.name || `${store.source.db_type} → ${store.target.db_type}`,
        source_db_type: store.source.db_type,
        target_db_type: store.target.db_type,
        // A saved connection is referenced by id so its credential is read
        // from Vault server-side; otherwise the typed string is vaulted now.
        ...(store.source.connection_id
          ? { source_connection_id: store.source.connection_id }
          : { source_connection_string: store.source.connection_string }),
        ...(store.target.connection_id
          ? { target_connection_id: store.target.connection_id }
          : { target_connection_string: store.target.connection_string }),
        options: {
          skip_tables: store.skipTables,
          conflict_strategy: store.conflictStrategy,
          dry_run: store.dryRun,
          chunk_size: store.chunkSize,
        },
      },
      {
        onSuccess: (job) => {
          startMigration.mutate(job.id, {
            onSuccess: () => {
              store.reset();
              navigate(`/migrations/${job.id}`);
            },
            onError: (error) => message.error(apiErrorMessage(error)),
          });
        },
        onError: (error) => message.error(apiErrorMessage(error)),
      },
    );
  };

  const difficulty = pairDifficulty(store.source.db_type, store.target.db_type);

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <div>
        <Title level={3} style={{ margin: 0, letterSpacing: '-0.02em' }}>
          New migration
        </Title>
        <Text type="secondary" style={{ fontSize: 13.5 }}>
          Three steps. The agent handles the rest.
        </Text>
      </div>

      <Steps
        current={store.step}
        onChange={(next) => {
          if (next < store.step || canLeaveStep) store.setStep(next);
        }}
        items={[
          { title: 'Source database' },
          { title: 'Target database' },
          { title: 'Options & launch' },
        ]}
      />

      {store.step === 0 ? (
        <ConnectionForm
          title="Where is your data now?"
          description="The agent reads the schema and samples real rows — nothing is written to the source."
          value={store.source}
          onChange={store.setSource}
        />
      ) : null}

      {store.step === 1 ? (
        <ConnectionForm
          title="Where should it go?"
          description="Tables or collections are created automatically from the AI migration plan."
          value={store.target}
          onChange={store.setTarget}
        />
      ) : null}

      {store.step === 2 ? (
        <Card variant="outlined" className="glass-panel" style={{ borderRadius: 14 }} styles={{ body: { padding: 24 } }}>
          <Space direction="vertical" size={22} style={{ width: '100%' }}>
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <DbPair source={store.source.db_type} target={store.target.db_type} />
              <Text type="secondary" style={{ fontSize: 12.5 }}>
                Difficulty: <Text strong>{difficulty}</Text>
              </Text>
            </Space>

            <div>
              <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
                Migration name
              </Text>
              <Input
                placeholder="e.g. Production MySQL → PostgreSQL"
                value={store.name}
                onChange={(e) => store.setName(e.target.value)}
              />
            </div>

            <Row gutter={[20, 20]}>
              <Col xs={24} md={12}>
                <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
                  Tables to skip
                </Text>
                <Select
                  mode="multiple"
                  allowClear
                  placeholder={
                    store.source.discovered_tables.length
                      ? 'Select tables to exclude'
                      : 'Run a source connection test to list tables'
                  }
                  style={{ width: '100%' }}
                  value={store.skipTables}
                  onChange={store.setSkipTables}
                  options={store.source.discovered_tables.map((t) => ({ value: t, label: t }))}
                />
              </Col>
              <Col xs={24} md={12}>
                <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
                  On conflict
                </Text>
                <Segmented
                  block
                  value={store.conflictStrategy}
                  onChange={(v) => store.setConflictStrategy(v as ConflictStrategy)}
                  options={[
                    { label: 'Skip duplicates', value: 'skip' },
                    { label: 'Overwrite', value: 'overwrite' },
                    { label: 'Fail on conflict', value: 'fail' },
                  ]}
                />
              </Col>
              <Col xs={24} md={12}>
                <Space size={10}>
                  <Switch checked={store.dryRun} onChange={store.setDryRun} />
                  <div>
                    <Text strong style={{ fontSize: 13, display: 'block' }}>
                      Dry run first
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12.5 }}>
                      Generate the plan and wait for your approval before touching the target.
                    </Text>
                  </div>
                </Space>
              </Col>
              <Col xs={24} md={12}>
                <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
                  Chunk size (rows per batch)
                </Text>
                <InputNumber
                  min={100}
                  max={100000}
                  step={100}
                  style={{ width: 180 }}
                  value={store.chunkSize}
                  onChange={(v) => store.setChunkSize(v ?? 1000)}
                />
              </Col>
            </Row>

            <Text type="secondary" style={{ fontSize: 12.5, color: brand.inkMuted }}>
              Recommendation: put your source database in read-only mode while the migration
              runs — writes during migration will not be captured.
            </Text>
          </Space>
        </Card>
      ) : null}

      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Button
          icon={<ArrowLeftOutlined />}
          disabled={store.step === 0}
          onClick={store.prevStep}
        >
          Back
        </Button>
        {store.step < 2 ? (
          <Button type="primary" disabled={!canLeaveStep} onClick={store.nextStep}>
            Continue <ArrowRightOutlined />
          </Button>
        ) : (
          <Button
            type="primary"
            icon={<RocketOutlined />}
            loading={createMigration.isPending || startMigration.isPending}
            onClick={submit}
          >
            {store.dryRun ? 'Generate plan' : 'Start migration'}
          </Button>
        )}
      </Space>
    </Space>
  );
}

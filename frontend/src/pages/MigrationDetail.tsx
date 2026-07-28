import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  App as AntApp,
  Alert,
  Button,
  Card,
  Skeleton,
  Space,
  Typography,
} from 'antd';
import {
  DownloadOutlined,
  MonitorOutlined,
  RedoOutlined,
  RollbackOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { DbPair } from '@/components/migration/DbBadge';
import { FinalReportCard } from '@/components/migration/FinalReportCard';
import { MigrationPlan } from '@/components/migration/MigrationPlan';
import { MigrationProgress } from '@/components/migration/MigrationProgress';
import { ValidationReport } from '@/components/migration/ValidationReport';
import { SemanticReportCard } from '@/components/migration/SemanticReportCard';
import { PreviewDiff } from '@/components/migration/PreviewDiff';
import { ConfidenceBreakdown } from '@/components/migration/ConfidenceBreakdown';
import { QualityReportCard } from '@/components/migration/QualityReportCard';
import { SimulationView } from '@/components/migration/SimulationView';
import { TablePlanCard } from '@/components/migration/TablePlanCard';
import { SharePanel } from '@/components/migration/SharePanel';
import { StatusBadge } from '@/components/migration/StatusBadge';
import {
  useApprovePlan,
  useCancelMigration,
  useConfidenceBreakdown,
  useEnrollMonitor,
  useMigrationDetail,
  usePreviewDiff,
  useResumeMigration,
  useRunSimulation,
  useSemanticReport,
  useStartMigration,
  useTablePlan,
} from '@/hooks/useMigration';
import { useMigrationRealtime } from '@/hooks/useMigrationRealtime';
import { api, apiErrorMessage } from '@/lib/api';
import { isActive } from '@/lib/utils';

const { Title } = Typography;

export function MigrationDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const { data: job, isLoading } = useMigrationDetail(id);
  const approvePlan = useApprovePlan();
  const cancelMigration = useCancelMigration();
  const startMigration = useStartMigration();

  useMigrationRealtime(id);

  // 404s until the profiler has run; only ask once the profile is stored.
  const { data: semanticReport } = useSemanticReport(
    id,
    Boolean(job?.data_profile),
  );
  const { data: previewDiff } = usePreviewDiff(id, Boolean(job?.data_profile));
  const { data: confidenceBreakdown } = useConfidenceBreakdown(
    id,
    Boolean(job?.validation_report),
  );
  const { data: tablePlan } = useTablePlan(id, Boolean(job?.migration_plan));
  // Quality and simulation ride along on the job payload — requesting them
  // separately 404s on every render until they exist, which is just noise.
  const qualityReport = job?.data_profile?.quality;
  const simulation = job?.simulation ?? undefined;
  const runSimulation = useRunSimulation();
  const resumeMigration = useResumeMigration();
  const enrollMonitor = useEnrollMonitor();

  // T1-3 — the approval button stays locked until mismatches are acknowledged.
  const [acknowledged, setAcknowledged] = useState(false);

  if (isLoading || !job) {
    return (
      <Card variant="outlined" className="glass-panel" style={{ borderRadius: 14 }}>
        <Skeleton active paragraph={{ rows: 6 }} />
      </Card>
    );
  }

  const validation = job.validation_report;

  const approveNow = () =>
    approvePlan.mutate(job.id, {
      onError: (e) => message.error(apiErrorMessage(e)),
    });

  const enrollMonitorNow = () =>
    enrollMonitor.mutate(
      { jobId: job.id },
      {
        onSuccess: () => {
          message.success('Baseline captured — drift monitoring is on.');
          navigate('/monitoring');
        },
        onError: (e) => message.error(apiErrorMessage(e)),
      },
    );

  const saveBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadRollback = async () => {
    try {
      const { data } = await api.get<Blob>(`/migrations/${job.id}/rollback-script`, {
        responseType: 'blob',
      });
      const ext = job.target_db_type.includes('mongo') ? 'js' : 'sql';
      saveBlob(data, `${job.name.replace(/\s+/g, '_')}_rollback.${ext}`);
    } catch (e) {
      message.error(apiErrorMessage(e));
    }
  };

  const downloadReport = async () => {
    const base = job.name.replace(/\s+/g, '_');
    try {
      const { data } = await api.get<Blob>(`/migrations/${job.id}/report/pdf`, {
        responseType: 'blob',
      });
      saveBlob(data, `${base}_report.pdf`);
    } catch {
      // PDF not available (e.g. older job without a final report) — fall back to JSON.
      saveBlob(
        new Blob([JSON.stringify({ job, validation }, null, 2)], {
          type: 'application/json',
        }),
        `${base}_report.json`,
      );
    }
  };

  // The plan cannot be approved while unreviewed mismatches exist (T1-3).
  const needsAcknowledgement =
    job.status === 'awaiting_approval' &&
    Boolean(previewDiff && previewDiff.differing_count > 0) &&
    !acknowledged;

  // The worker touches updated_at on every chunk; a long-silent active job
  // means the worker likely died. The backend marks it failed after 5 minutes.
  const workerSilentMs = Date.now() - new Date(job.updated_at).getTime();
  const workerStale = isActive(job.status) && workerSilentMs > 120_000;

  return (
    <Space direction="vertical" size={20} style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }} align="start">
        <Space direction="vertical" size={8}>
          <Title level={3} style={{ margin: 0, letterSpacing: '-0.02em' }}>
            {job.name}
          </Title>
          <DbPair source={job.source_db_type} target={job.target_db_type} />
        </Space>
        <Space>
          {isActive(job.status) || job.status === 'pending' ? (
            <Button
              danger
              icon={<StopOutlined />}
              loading={cancelMigration.isPending}
              onClick={() =>
                cancelMigration.mutate(job.id, {
                  onError: (e) => message.error(apiErrorMessage(e)),
                })
              }
            >
              Cancel
            </Button>
          ) : null}
          {job.status === 'failed' || job.status === 'cancelled' ? (
            <Button
              type="primary"
              icon={<RedoOutlined />}
              loading={startMigration.isPending}
              onClick={() =>
                startMigration.mutate(job.id, {
                  onError: (e) => message.error(apiErrorMessage(e)),
                })
              }
            >
              Try again
            </Button>
          ) : null}
          {job.migration_plan ? (
            <Button icon={<RollbackOutlined />} onClick={downloadRollback}>
              Rollback script
            </Button>
          ) : null}
          {job.status === 'completed' ? (
            <Button
              icon={<MonitorOutlined />}
              loading={enrollMonitor.isPending}
              onClick={enrollMonitorNow}
            >
              Monitor for drift
            </Button>
          ) : null}
          {job.status === 'completed' ? (
            <Button icon={<DownloadOutlined />} onClick={downloadReport}>
              Download report
            </Button>
          ) : null}
          <StatusBadge status={job.status} />
        </Space>
      </Space>

      <MigrationProgress job={job} tablePlan={tablePlan} />

      {workerStale ? (
        <Alert
          type="warning"
          showIcon
          message="Worker unresponsive"
          description="No progress updates for over 2 minutes. If the worker crashed, the job will be marked failed automatically and can be restarted."
        />
      ) : null}

      {job.status === 'awaiting_approval' &&
      job.migration_plan &&
      !approvePlan.isPending &&
      !approvePlan.isSuccess ? (
        <Alert
          type="warning"
          showIcon
          message="The AI plan is ready for review"
          description={
            needsAcknowledgement
              ? `Nothing has been written to the target. Review the ${previewDiff?.differing_count} schema/data mismatches below and confirm you have seen them to unlock execution.`
              : 'Nothing has been written to the target. Approve the plan below to execute.'
          }
          action={
            // With mismatches present the approval control lives inside the diff,
            // right under the rows it is gating. Only offer it here when there is
            // nothing to acknowledge.
            needsAcknowledgement || previewDiff?.differing_count ? undefined : (
              <Button
                type="primary"
                loading={approvePlan.isPending}
                onClick={approveNow}
              >
                Approve &amp; execute
              </Button>
            )
          }
        />
      ) : null}

      {job.status === 'failed' && job.error_log.length > 0 ? (
        <Alert
          type="error"
          showIcon
          message="Migration failed"
          description={String(
            typeof job.error_log[job.error_log.length - 1] === 'object'
              ? (job.error_log[job.error_log.length - 1] as { error?: string }).error
              : job.error_log[job.error_log.length - 1],
          )}
        />
      ) : null}

      {semanticReport ? (
        <SemanticReportCard jobName={job.name} report={semanticReport} />
      ) : null}

      {qualityReport ? <QualityReportCard report={qualityReport} /> : null}

      {previewDiff ? (
        <PreviewDiff
          diff={previewDiff}
          acknowledged={acknowledged}
          onAcknowledge={
            job.status === 'awaiting_approval' ? setAcknowledged : undefined
          }
          onApprove={job.status === 'awaiting_approval' ? approveNow : undefined}
          approving={approvePlan.isPending}
        />
      ) : null}

      {job.migration_plan ? <MigrationPlan plan={job.migration_plan} /> : null}

      {job.migration_plan ? (
        <SimulationView
          simulation={simulation}
          running={runSimulation.isPending}
          onRun={() =>
            runSimulation.mutate(job.id, {
              onSuccess: () =>
                message.info('Simulation queued — results appear in a few seconds.'),
              onError: (e) => message.error(apiErrorMessage(e)),
            })
          }
        />
      ) : null}

      {tablePlan ? (
        <TablePlanCard
          plan={tablePlan}
          resuming={resumeMigration.isPending}
          canResume={job.status === 'failed' || job.status === 'cancelled'}
          onResume={(tables) =>
            resumeMigration.mutate(
              { id: job.id, onlyTables: tables },
              {
                onSuccess: (r: { detail?: string }) =>
                  message.success(r?.detail ?? 'Resuming migration'),
                onError: (e) => message.error(apiErrorMessage(e)),
              },
            )
          }
        />
      ) : null}

      {validation ? (
        <ValidationReport
          report={validation}
          onDownloadPdf={downloadReport}
          onShare={
            job.status === 'completed'
              ? () =>
                  document
                    .getElementById('share-panel')
                    ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
              : undefined
          }
          onMonitor={job.status === 'completed' ? enrollMonitorNow : undefined}
          monitoring={enrollMonitor.isPending}
        />
      ) : null}

      {confidenceBreakdown ? (
        <ConfidenceBreakdown breakdown={confidenceBreakdown} />
      ) : null}

      {job.final_report ? (
        <FinalReportCard jobId={job.id} jobName={job.name} report={job.final_report} />
      ) : null}

      {job.status === 'completed' ? (
        <div id="share-panel">
          <SharePanel jobId={job.id} />
        </div>
      ) : null}
    </Space>
  );
}

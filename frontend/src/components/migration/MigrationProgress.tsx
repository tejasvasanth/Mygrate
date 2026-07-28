import { useEffect, useState } from 'react';
import {
  Boxes,
  Brain,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  Database,
  Gauge,
  Layers,
  Loader2,
  Microscope,
  ShieldCheck,
  Table2,
  XCircle,
  Zap,
} from 'lucide-react';
import { ProgressTerminal } from '@/components/migration/ProgressTerminal';
import { formatFullNumber } from '@/lib/utils';
import type { MigrationJob, TablePlanResponse } from '@/types';

/** The five agents, in the order the worker runs them. */
const STEPS = [
  { key: 'analyzing', label: 'Schema Analyst', icon: Database },
  { key: 'profiling', label: 'Data Profiler', icon: Microscope },
  { key: 'planning', label: 'Mapping Strategist', icon: Brain },
  { key: 'executing', label: 'Executor', icon: Boxes },
  { key: 'validating', label: 'Validation Auditor', icon: ShieldCheck },
] as const;

/**
 * How far the pipeline has advanced. `awaiting_approval` sits between planning
 * and executing, so it counts the first three as done without lighting up the
 * executor — the user, not the worker, is the blocker at that point.
 */
function pipelineIndex(status: MigrationJob['status']): number {
  switch (status) {
    case 'pending':
      return -1;
    case 'analyzing':
      return 0;
    case 'profiling':
      return 1;
    case 'planning':
      return 2;
    case 'awaiting_approval':
      return 2.5;
    case 'executing':
      return 3;
    case 'validating':
      return 4;
    case 'completed':
      return 5;
    default:
      // failed / cancelled — freeze the stepper where it stopped.
      return -2;
  }
}

function Stepper({ job }: { job: MigrationJob }) {
  const index = pipelineIndex(job.status);
  const halted = job.status === 'failed' || job.status === 'cancelled';

  return (
    <ol className="flex flex-col gap-4 md:flex-row md:gap-0">
      {STEPS.map((step, i) => {
        const done = index > i;
        const active = index === i;
        const waiting = index === 2.5 && i === 3;
        const Icon = step.icon;

        const ring = halted
          ? 'border-slate-200 bg-white text-slate-300'
          : done
            ? 'border-green-600 bg-green-600 text-white'
            : active
              ? 'border-blue-500 bg-blue-50 text-blue-600'
              : waiting
                ? 'border-amber-400 bg-amber-50 text-amber-600'
                : 'border-slate-200 bg-white text-slate-300';

        return (
          <li
            key={step.key}
            className="relative flex flex-1 items-center gap-3 md:flex-col md:items-center md:gap-2"
          >
            {/* Connector to the next step — drawn behind the circle row so it
                never shifts the layout. Horizontal on desktop only. */}
            {i < STEPS.length - 1 ? (
              <span
                aria-hidden
                className={`absolute hidden h-0.5 md:block ${
                  done ? 'bg-green-500' : 'bg-slate-200'
                }`}
                style={{ top: 19, left: 'calc(50% + 24px)', right: 'calc(-50% + 24px)' }}
              />
            ) : null}

            <span className="relative z-10 flex shrink-0">
              {active && !halted ? (
                <span className="absolute inset-0 animate-ping rounded-full bg-blue-400/40" />
              ) : null}
              <span
                className={`relative flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors ${ring}`}
              >
                {done ? <CheckCircle2 size={18} /> : <Icon size={18} />}
              </span>
            </span>

            <div className="md:text-center">
              <div
                className={`text-[12.5px] font-semibold ${
                  done || active
                    ? 'text-[#0F1B14]'
                    : waiting
                      ? 'text-amber-700'
                      : 'text-slate-400'
                }`}
              >
                {step.label}
              </div>
              <div className="text-[11px] text-[#7C8A83]">
                {halted && !done
                  ? '—'
                  : done
                    ? 'complete'
                    : active
                      ? 'running'
                      : waiting
                        ? 'awaiting approval'
                        : 'pending'}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function StatTile({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-[#E4EDE7] bg-white/80 p-3.5">
      <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-[#7C8A83]">
        <span className="text-green-600">{icon}</span>
        {label}
      </div>
      <div className="mt-1.5 text-[20px] font-semibold tabular-nums leading-none text-[#0F1B14]">
        {value}
      </div>
      {hint ? <div className="mt-1 text-[11px] text-[#7C8A83]">{hint}</div> : null}
    </div>
  );
}

/** Ticks once a second so elapsed time and rows/sec stay live between polls. */
function useTicker(enabled: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [enabled]);
  return now;
}

function elapsedLabel(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`;
  if (m > 0) return `${m}m ${String(s).padStart(2, '0')}s`;
  return `${s}s`;
}

/**
 * The live view of a running migration: what the pipeline is doing, how far it
 * has got, and the raw agent log underneath it.
 */
export function MigrationProgress({
  job,
  tablePlan,
}: {
  job: MigrationJob;
  tablePlan?: TablePlanResponse;
}) {
  const running =
    job.status !== 'completed' && job.status !== 'failed' && job.status !== 'cancelled';
  const now = useTicker(running);

  const startedMs = job.started_at ? new Date(job.started_at).getTime() : null;
  const endMs = job.completed_at ? new Date(job.completed_at).getTime() : now;
  const elapsedSec = startedMs ? Math.max(0, (endMs - startedMs) / 1000) : 0;
  const rowsPerSec = elapsedSec > 0 ? job.rows_migrated / elapsedSec : 0;

  const tables = tablePlan?.tables ?? [];
  const tablesDone = tables.filter(
    (t) => t.status === 'migrated' || t.status === 'validated',
  ).length;
  const currentTable = tables.find((t) => t.status === 'migrating');

  // The executor commits one chunk at a time; chunk size is per-job.
  const chunkSize = job.options?.chunk_size || 1000;
  const chunksCommitted = Math.floor(job.rows_migrated / chunkSize);

  const remainingRows = Math.max(0, job.rows_total - job.rows_migrated);
  const etaSec = rowsPerSec > 0.01 ? remainingRows / rowsPerSec : null;

  const failed = job.status === 'failed' || job.status === 'cancelled';
  const barColor = failed
    ? 'bg-red-500'
    : job.status === 'completed'
      ? 'bg-green-600'
      : 'bg-green-500';

  return (
    <section className="overflow-hidden rounded-2xl border border-[#E4EDE7] bg-white shadow-sm">
      {/* ── Pipeline stepper ──────────────────────────────────────── */}
      <div className="border-b border-[#E4EDE7] bg-[#F7FAF8] px-6 py-6">
        <Stepper job={job} />
      </div>

      <div className="grid grid-cols-1 gap-6 p-6 xl:grid-cols-[1fr_260px]">
        <div className="min-w-0">
          {/* ── Progress bar ────────────────────────────────────── */}
          <div className="flex items-end justify-between gap-4">
            <div>
              <div className="text-[26px] font-bold leading-none tabular-nums text-[#0F1B14]">
                {formatFullNumber(job.rows_migrated)}
                <span className="text-[15px] font-medium text-[#7C8A83]">
                  {' / '}
                  {formatFullNumber(job.rows_total)} rows
                </span>
              </div>
              <div className="mt-1.5 flex items-center gap-2 text-[12.5px] text-[#4B5A52]">
                {currentTable ? (
                  <>
                    <Loader2 size={13} className="animate-spin text-green-600" />
                    Migrating{' '}
                    <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[12px]">
                      {currentTable.table}
                    </code>
                    <span className="text-[#7C8A83]">
                      → {currentTable.target_table}
                    </span>
                  </>
                ) : failed ? (
                  <>
                    <XCircle size={13} className="text-red-500" />
                    Stopped
                  </>
                ) : job.status === 'completed' ? (
                  <>
                    <CheckCircle2 size={13} className="text-green-600" />
                    All tables migrated
                  </>
                ) : (
                  <>
                    <Loader2 size={13} className="animate-spin text-green-600" />
                    {job.status === 'awaiting_approval'
                      ? 'Waiting for your approval'
                      : 'Working…'}
                  </>
                )}
              </div>
            </div>
            <div
              className={`text-[32px] font-bold leading-none tabular-nums ${
                failed ? 'text-red-600' : 'text-green-600'
              }`}
            >
              {Math.round(job.progress_pct)}
              <span className="text-[18px]">%</span>
            </div>
          </div>

          <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-full rounded-full transition-[width] duration-700 ease-out ${barColor} ${
                running ? 'sheen' : ''
              }`}
              style={{ width: `${Math.min(100, Math.max(0, job.progress_pct))}%` }}
              role="progressbar"
              aria-valuenow={Math.round(job.progress_pct)}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>

          {/* ── Live log ────────────────────────────────────────── */}
          <div className="mt-6">
            <ProgressTerminal jobId={job.id} />
          </div>
        </div>

        {/* ── Live stats sidebar ────────────────────────────────── */}
        <aside className="grid grid-cols-2 gap-3 xl:grid-cols-1 xl:content-start">
          <StatTile
            icon={<Clock size={13} />}
            label="Elapsed"
            value={startedMs ? elapsedLabel(elapsedSec) : '—'}
            hint={
              etaSec !== null && running && job.rows_total > 0
                ? `~${elapsedLabel(etaSec)} remaining`
                : undefined
            }
          />
          <StatTile
            icon={<Zap size={13} />}
            label="Throughput"
            value={
              rowsPerSec > 0
                ? `${rowsPerSec >= 100 ? Math.round(rowsPerSec) : rowsPerSec.toFixed(1)}/s`
                : '—'
            }
            hint="rows per second"
          />
          <StatTile
            icon={<Table2 size={13} />}
            label="Tables"
            value={tables.length > 0 ? `${tablesDone} / ${tables.length}` : '—'}
            hint={tables.length > 0 ? 'complete' : 'plan not built yet'}
          />
          <StatTile
            icon={<Layers size={13} />}
            label="Chunks"
            value={formatFullNumber(chunksCommitted)}
            hint={`committed · ${formatFullNumber(chunkSize)}/chunk`}
          />
          <div className="col-span-2 rounded-xl border border-[#E4EDE7] bg-[#F7FAF8] p-3.5 xl:col-span-1">
            <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-[#7C8A83]">
              <Gauge size={13} className="text-green-600" />
              Conflict strategy
            </div>
            <div className="mt-1.5 text-[13px] font-medium capitalize text-[#0F1B14]">
              {job.options?.conflict_strategy ?? 'skip'} duplicates
            </div>
            <div className="mt-2 flex items-center gap-1.5 text-[11.5px] text-[#7C8A83]">
              <ClipboardCheck size={12} />
              Progress is checkpointed — a failed job resumes from the last committed
              chunk.
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

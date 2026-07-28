import { useState } from 'react';
import {
  AlertTriangle,
  ChevronDown,
  Download,
  Eye,
  Fingerprint,
  Hash,
  Link2,
  ListFilter,
  ShieldAlert,
  ToggleLeft,
} from 'lucide-react';
import { ScoreGauge, toneFor, TONE_HEX } from '@/components/ui/ScoreGauge';
import type {
  DangerousMismatch,
  ImplicitBooleanFinding,
  ImplicitEnumFinding,
  ImplicitForeignKey,
  PiiFinding,
  SemanticDetection,
  SemanticFinding,
  SemanticReport,
} from '@/types';

/** Finding severity → the visual language used across every card and pill. */
type Severity = 'danger' | 'mismatch' | 'pii' | 'info';

const SEVERITY: Record<
  Severity,
  { border: string; bg: string; text: string; chip: string }
> = {
  danger: {
    border: 'border-l-red-600',
    bg: 'bg-red-50/60',
    text: 'text-red-700',
    chip: 'bg-red-100 text-red-700',
  },
  mismatch: {
    border: 'border-l-amber-500',
    bg: 'bg-amber-50/50',
    text: 'text-amber-700',
    chip: 'bg-amber-100 text-amber-800',
  },
  pii: {
    border: 'border-l-blue-500',
    bg: 'bg-blue-50/50',
    text: 'text-blue-700',
    chip: 'bg-blue-100 text-blue-700',
  },
  info: {
    border: 'border-l-slate-300',
    bg: 'bg-slate-50/60',
    text: 'text-slate-600',
    chip: 'bg-slate-100 text-slate-600',
  },
};

function ConfidencePill({ value }: { value: number }) {
  const cls =
    value >= 95
      ? 'bg-green-100 text-green-800'
      : value >= 80
        ? 'bg-amber-100 text-amber-800'
        : 'bg-red-100 text-red-700';
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ${cls}`}>
      {Math.round(value)}%
    </span>
  );
}

function ColumnRef({ table, column }: { table: string; column: string }) {
  return (
    <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[12.5px] text-slate-800">
      <span className="text-slate-500">{table}.</span>
      {column}
    </code>
  );
}

function TypeChip({ label, tone }: { label: string; tone: 'declared' | 'inferred' }) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 font-mono text-[11.5px] ${
        tone === 'declared'
          ? 'bg-slate-100 text-slate-600 line-through decoration-slate-400'
          : 'bg-green-100 font-semibold text-green-800'
      }`}
    >
      {label}
    </span>
  );
}

/** One tile in the findings grid. Collapsed it is a count; open it is evidence. */
function FindingCard({
  icon,
  title,
  count,
  severity,
  blurb,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  count: number;
  severity: Severity;
  blurb: string;
  children?: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const s = SEVERITY[severity];
  const empty = count === 0;
  const expandable = Boolean(children) && !empty;

  return (
    <div
      className={`overflow-hidden rounded-xl border border-[#E4EDE7] border-l-4 transition-colors ${
        empty ? 'border-l-slate-200 bg-white/70' : `${s.border} ${s.bg}`
      }`}
    >
      <button
        type="button"
        disabled={!expandable}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={`flex w-full items-start gap-3 p-4 text-left ${
          expandable ? 'cursor-pointer hover:bg-white/50' : 'cursor-default'
        }`}
      >
        <span className={`mt-0.5 shrink-0 ${empty ? 'text-slate-300' : s.text}`}>
          {icon}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="text-[13px] font-semibold text-[#0F1B14]">{title}</span>
            {expandable ? (
              <ChevronDown
                size={14}
                className={`text-slate-400 transition-transform duration-200 ${
                  open ? 'rotate-180' : ''
                }`}
              />
            ) : null}
          </span>
          <span
            className={`mt-1 block text-[28px] font-bold leading-none tabular-nums ${
              empty ? 'text-slate-300' : s.text
            }`}
          >
            {count}
          </span>
          <span className="mt-1.5 block text-[11.5px] leading-snug text-[#7C8A83]">
            {empty ? 'None found' : blurb}
          </span>
        </span>
      </button>
      {open && expandable ? (
        <div className="border-t border-[#E4EDE7] bg-white/80 px-4 py-3">{children}</div>
      ) : null}
    </div>
  );
}

/** Compact evidence list used inside expanded finding cards. */
function DetailRow({
  left,
  right,
}: {
  left: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-100 py-1.5 last:border-0">
      <div className="flex min-w-0 flex-wrap items-center gap-2">{left}</div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </div>
  );
}

export function SemanticReportCard({
  jobName,
  report,
}: {
  jobName: string;
  report: SemanticReport;
}) {
  const score = report.schema_trust_score;
  const { summary } = report;
  const tone = toneFor(score, 60, 85);
  const scoreLabel =
    tone === 'green' ? 'Trustworthy' : tone === 'amber' ? 'Needs review' : 'High risk';

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${jobName.replace(/\s+/g, '_')}_semantic_report.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="overflow-hidden rounded-2xl border border-[#E4EDE7] bg-white shadow-sm">
      {/* ── Dark header: the headline number, before any detail ─────── */}
      <header className="relative flex flex-wrap items-center justify-between gap-4 bg-[#0F1B14] px-6 py-5">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px)',
            backgroundSize: '32px 32px',
          }}
        />
        <div className="relative">
          <h2 className="text-lg font-semibold tracking-tight text-white">
            Schema Trust Report
          </h2>
          <p className="mt-1 max-w-xl text-[13px] leading-snug text-white/55">
            We read {summary.total_columns_profiled.toLocaleString()} columns of actual
            data — not just the declared types — and found{' '}
            {summary.total_mismatches.toLocaleString()} place
            {summary.total_mismatches === 1 ? '' : 's'} where your schema and your data
            disagree.
          </p>
        </div>
        <div className="relative flex items-center gap-5">
          <div className="text-right">
            <div
              className="text-[52px] font-bold leading-none tabular-nums"
              style={{ color: TONE_HEX[tone], letterSpacing: '-0.04em' }}
            >
              {Math.round(score)}
            </div>
            <div
              className="mt-1 inline-block rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide"
              style={{ background: `${TONE_HEX[tone]}22`, color: TONE_HEX[tone] }}
            >
              {scoreLabel}
            </div>
          </div>
          <button
            type="button"
            onClick={exportJson}
            className="flex items-center gap-1.5 rounded-lg border border-white/20 px-3 py-1.5 text-[12.5px] font-medium text-white/80 transition-colors hover:border-white/40 hover:text-white"
          >
            <Download size={14} />
            Export JSON
          </button>
        </div>
      </header>

      <div className="p-6">
        {/* ── Gauge + findings grid ─────────────────────────────────── */}
        <div className="flex flex-col gap-8 lg:flex-row lg:items-start">
          <div className="mx-auto shrink-0 lg:mx-0">
            <ScoreGauge
              score={score}
              tone={tone}
              size={190}
              caption="out of 100"
              label="Schema trust score"
            />
            <p className="mt-2 max-w-[190px] text-center text-[11.5px] leading-snug text-[#7C8A83]">
              100 means every declared type matches what the data actually contains.
            </p>
          </div>

          <div className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <FindingCard
              icon={<ShieldAlert size={18} />}
              title="Data loss risk"
              count={summary.dangerous_mismatch_count}
              severity="danger"
              blurb="Types that silently destroy data on migration"
            >
              {report.dangerous_type_mismatches.map((f: DangerousMismatch) => (
                <DetailRow
                  key={`${f.table}.${f.column}`}
                  left={
                    <>
                      <ColumnRef table={f.table} column={f.column} />
                      <span className="text-[12px] text-red-700">{f.risk}</span>
                    </>
                  }
                  right={<ConfidencePill value={f.confidence_pct} />}
                />
              ))}
            </FindingCard>

            <FindingCard
              icon={<ToggleLeft size={18} />}
              title="Implicit Booleans"
              count={summary.implicit_boolean_count}
              severity="mismatch"
              blurb="Numeric columns that only ever hold 0 and 1"
            >
              {report.implicit_booleans.map((f: ImplicitBooleanFinding) => (
                <DetailRow
                  key={`${f.table}.${f.column}`}
                  left={
                    <>
                      <ColumnRef table={f.table} column={f.column} />
                      <TypeChip label={f.declared_type ?? 'unknown'} tone="declared" />
                      <TypeChip label="boolean" tone="inferred" />
                      <span className="font-mono text-[11px] text-slate-500">
                        {f.sample_values.join(' · ')}
                      </span>
                    </>
                  }
                  right={<ConfidencePill value={f.confidence} />}
                />
              ))}
            </FindingCard>

            <FindingCard
              icon={<ListFilter size={18} />}
              title="Implicit Enums"
              count={summary.implicit_enum_count}
              severity="mismatch"
              blurb="Free-text columns with a small fixed value set"
            >
              {report.implicit_enums.map((f: ImplicitEnumFinding) => (
                <DetailRow
                  key={`${f.table}.${f.column}`}
                  left={
                    <>
                      <ColumnRef table={f.table} column={f.column} />
                      <span className="flex flex-wrap gap-1">
                        {f.distinct_values.slice(0, 6).map((v) => (
                          <span
                            key={v}
                            className="rounded bg-green-100 px-1.5 py-0.5 font-mono text-[11px] text-green-800"
                          >
                            {v}
                          </span>
                        ))}
                        {f.distinct_count > 6 ? (
                          <span className="text-[11px] text-slate-500">
                            +{f.distinct_count - 6} more
                          </span>
                        ) : null}
                      </span>
                    </>
                  }
                  right={<ConfidencePill value={f.confidence} />}
                />
              ))}
            </FindingCard>

            <FindingCard
              icon={<Fingerprint size={18} />}
              title="Semantic types"
              count={summary.semantic_detection_count}
              severity="mismatch"
              blurb="Text and numbers that are really something specific"
            >
              {report.semantic_detections.map((f: SemanticDetection) => (
                <DetailRow
                  key={`${f.table}.${f.column}`}
                  left={
                    <>
                      <ColumnRef table={f.table} column={f.column} />
                      <TypeChip label={f.declared_type ?? 'unknown'} tone="declared" />
                      <TypeChip label={f.inferred_semantic_type} tone="inferred" />
                      <span className="text-[11.5px] text-slate-500">
                        {f.evidence_summary}
                      </span>
                    </>
                  }
                  right={<ConfidencePill value={f.confidence_pct} />}
                />
              ))}
            </FindingCard>

            <FindingCard
              icon={<Hash size={18} />}
              title="Never-null nullables"
              count={summary.never_null_nullable_count}
              severity="info"
              blurb="Declared nullable, never null in the sample"
            >
              {report.never_null_nullables.map((f: SemanticFinding) => (
                <DetailRow
                  key={`${f.table}.${f.column}`}
                  left={
                    <>
                      <ColumnRef table={f.table} column={f.column} />
                      <span className="text-[11.5px] text-slate-500">
                        {f.sample_size.toLocaleString()} rows sampled, 0 nulls — consider
                        NOT NULL
                      </span>
                    </>
                  }
                />
              ))}
            </FindingCard>

            <FindingCard
              icon={<Eye size={18} />}
              title="PII columns"
              count={summary.pii_column_count}
              severity="pii"
              blurb="Personal data found — handle deliberately"
            >
              {report.pii_columns.map((f: PiiFinding) => (
                <DetailRow
                  key={`${f.table}.${f.column}`}
                  left={
                    <>
                      <ColumnRef table={f.table} column={f.column} />
                      <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                        {f.pii_type.replace(/_/g, ' ')}
                      </span>
                    </>
                  }
                />
              ))}
            </FindingCard>
          </div>
        </div>

        {/* ── Data loss panel — the one thing that must not be missed ── */}
        {report.dangerous_type_mismatches.length > 0 ? (
          <div className="mt-6 overflow-hidden rounded-xl border border-red-300 bg-red-50/70">
            <div className="flex items-start gap-3 border-b border-red-200 px-5 py-3.5">
              <AlertTriangle size={18} className="mt-0.5 shrink-0 text-red-600" />
              <div>
                <h3 className="text-sm font-semibold text-red-800">
                  Data Loss Risk — review before migrating
                </h3>
                <p className="mt-0.5 text-[12.5px] leading-snug text-red-700/80">
                  Migrating these columns with their declared types will silently corrupt
                  or truncate real values.
                </p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-[13px]">
                <thead>
                  <tr className="text-[11px] uppercase tracking-wide text-red-700/70">
                    <th className="px-5 py-2 font-semibold">Column</th>
                    <th className="px-5 py-2 font-semibold">Declared</th>
                    <th className="px-5 py-2 font-semibold">Actually is</th>
                    <th className="px-5 py-2 font-semibold">Risk</th>
                    <th className="px-5 py-2 font-semibold">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {report.dangerous_type_mismatches.map((f) => (
                    <tr
                      key={`${f.table}.${f.column}`}
                      className="border-t border-red-200/70"
                    >
                      <td className="px-5 py-2.5">
                        <ColumnRef table={f.table} column={f.column} />
                      </td>
                      <td className="px-5 py-2.5">
                        <TypeChip label={f.declared_type ?? 'unknown'} tone="declared" />
                      </td>
                      <td className="px-5 py-2.5">
                        <TypeChip label={f.inferred_semantic_type} tone="inferred" />
                      </td>
                      <td className="px-5 py-2.5 font-medium text-red-700">{f.risk}</td>
                      <td className="px-5 py-2.5">
                        <ConfidencePill value={f.confidence_pct} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {/* ── Implicit foreign keys ─────────────────────────────────── */}
        {report.implicit_foreign_keys.length > 0 ? (
          <div className="mt-6 overflow-hidden rounded-xl border border-[#E4EDE7]">
            <div className="flex items-start gap-3 border-b border-[#E4EDE7] bg-slate-50/70 px-5 py-3.5">
              <Link2 size={18} className="mt-0.5 shrink-0 text-amber-600" />
              <div>
                <h3 className="text-sm font-semibold text-[#0F1B14]">
                  Implicit Foreign Keys
                </h3>
                <p className="mt-0.5 text-[12.5px] leading-snug text-[#7C8A83]">
                  Relationships your schema never declared. We will preserve load order
                  for these so referencing rows land after the rows they point at.
                </p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-[13px]">
                <thead>
                  <tr className="text-[11px] uppercase tracking-wide text-[#7C8A83]">
                    <th className="px-5 py-2 font-semibold">Column</th>
                    <th className="px-5 py-2 font-semibold">Likely references</th>
                    <th className="px-5 py-2 font-semibold">Evidence</th>
                    <th className="px-5 py-2 font-semibold">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {report.implicit_foreign_keys.map((f: ImplicitForeignKey) => (
                    <tr
                      key={`${f.table}.${f.column}`}
                      className="border-t border-[#E4EDE7]"
                    >
                      <td className="px-5 py-2.5">
                        <ColumnRef table={f.table} column={f.column} />
                      </td>
                      <td className="px-5 py-2.5">
                        <code className="rounded bg-green-50 px-1.5 py-0.5 font-mono text-[12.5px] text-green-800">
                          {f.likely_references}
                        </code>
                      </td>
                      <td className="px-5 py-2.5 text-[12.5px] text-[#7C8A83]">
                        values match in {Math.round(f.match_pct)}% of sampled rows
                        {f.name_match ? ', and the column name matches the table' : ''}
                      </td>
                      <td className="px-5 py-2.5">
                        <ConfidencePill value={f.match_pct} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

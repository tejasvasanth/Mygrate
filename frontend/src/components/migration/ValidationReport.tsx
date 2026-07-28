import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Loader2,
  Radar,
  Share2,
  XCircle,
} from 'lucide-react';
import { ScoreGauge, toneFor } from '@/components/ui/ScoreGauge';
import { formatFullNumber } from '@/lib/utils';
import type { ValidationReport as ValidationReportData } from '@/types';

/** A table's verdict, normalised from either backend shape. */
interface TableResult {
  table: string;
  sourceRows: number;
  targetRows: number;
  mismatchPct: number;
  ok: boolean;
  fkOk: boolean | null;
  sampleHash: { sampled: number; matched: number } | null;
}

/** Row counts within 0.1% are treated as a match, per god.md §6. */
const MISMATCH_THRESHOLD = 0.1;

function normalise(report: ValidationReportData): TableResult[] {
  if (report.tables) {
    return Object.entries(report.tables).map(([table, v]) => {
      const pct =
        v.mismatch_pct ??
        (v.source_rows > 0
          ? (Math.abs(v.source_rows - v.target_rows) / v.source_rows) * 100
          : v.target_rows === 0
            ? 0
            : 100);
      return {
        table: v.target_table ?? table,
        sourceRows: v.source_rows,
        targetRows: v.target_rows,
        mismatchPct: pct,
        ok: v.row_count_ok ?? pct <= MISMATCH_THRESHOLD,
        fkOk: v.fk_integrity_ok ?? null,
        sampleHash: v.sample_hash
          ? { sampled: v.sample_hash.sampled, matched: v.sample_hash.matched }
          : null,
      };
    });
  }
  return (report.row_count_checks ?? []).map((c) => ({
    table: c.table,
    sourceRows: c.source_rows,
    targetRows: c.target_rows,
    mismatchPct:
      c.source_rows > 0
        ? (Math.abs(c.source_rows - c.target_rows) / c.source_rows) * 100
        : 0,
    ok: c.match,
    fkOk: null,
    sampleHash: null,
  }));
}

const TH =
  'px-5 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-[#7C8A83]';

/**
 * The completion screen. It has to answer one question in the first second:
 * can I trust that my data actually made it?
 */
export function ValidationReport({
  report,
  onDownloadPdf,
  onShare,
  onMonitor,
  monitoring,
  downloading,
}: {
  report: ValidationReportData;
  onDownloadPdf?: () => void;
  onShare?: () => void;
  onMonitor?: () => void;
  monitoring?: boolean;
  downloading?: boolean;
}) {
  const score = report.confidence_score;
  const tone = toneFor(score, 85, 95);
  const results = normalise(report);
  const failing = results.filter((r) => !r.ok);
  const flagged = new Set(report.flagged_tables ?? failing.map((r) => r.table));

  const headline =
    tone === 'green'
      ? 'Migration verified'
      : tone === 'amber'
        ? 'Migration completed with warnings'
        : 'Migration needs manual review';

  const subhead =
    tone === 'green'
      ? 'Row counts, sample hashes and referential integrity all check out.'
      : tone === 'amber'
        ? 'Most checks passed, but some tables need a look before you cut over.'
        : 'Several verification checks failed. Do not cut over until these are resolved.';

  return (
    <section className="overflow-hidden rounded-2xl border border-[#E4EDE7] bg-white shadow-sm">
      {/* ── Hero ──────────────────────────────────────────────────── */}
      <div className="flex flex-col items-center gap-8 border-b border-[#E4EDE7] bg-gradient-to-b from-[#F7FAF8] to-white px-6 py-8 md:flex-row md:items-center md:justify-center md:gap-12">
        <ScoreGauge score={score} tone={tone} size={168} suffix="%" caption="confidence" />
        <div className="max-w-md text-center md:text-left">
          <div className="flex items-center justify-center gap-2 md:justify-start">
            {tone === 'green' ? (
              <CheckCircle2 size={22} className="text-green-600" />
            ) : tone === 'amber' ? (
              <AlertTriangle size={22} className="text-amber-500" />
            ) : (
              <XCircle size={22} className="text-red-600" />
            )}
            <h2 className="text-xl font-semibold tracking-tight text-[#0F1B14]">
              {headline}
            </h2>
          </div>
          <p className="mt-2 text-[13.5px] leading-relaxed text-[#4B5A52]">{subhead}</p>
          <div className="mt-4 flex flex-wrap justify-center gap-2 md:justify-start">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-[12px] font-medium text-[#4B5A52]">
              {results.length} table{results.length === 1 ? '' : 's'} verified
            </span>
            {report.hash_checks_total ? (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-[12px] font-medium text-[#4B5A52]">
                {report.hash_checks_passed}/{report.hash_checks_total} sample hashes
                matched
              </span>
            ) : null}
            <span
              className={`rounded-full px-3 py-1 text-[12px] font-medium ${
                failing.length === 0
                  ? 'bg-green-100 text-green-800'
                  : 'bg-red-100 text-red-700'
              }`}
            >
              {failing.length === 0
                ? 'No row-count mismatches'
                : `${failing.length} table${failing.length === 1 ? '' : 's'} mismatched`}
            </span>
          </div>
        </div>
      </div>

      {/* ── Per-table results ─────────────────────────────────────── */}
      {results.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-[13px]">
            <thead className="bg-[#F7FAF8]">
              <tr>
                <th className={TH}>Table</th>
                <th className={TH}>Source rows</th>
                <th className={TH}>Target rows</th>
                <th className={TH}>Match</th>
                <th className={TH}>Integrity</th>
                <th className={TH}>Status</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr
                  key={r.table}
                  className={`border-t border-[#E4EDE7] ${
                    r.ok ? 'hover:bg-green-50/40' : 'bg-red-50/60'
                  }`}
                >
                  <td className="px-5 py-2.5">
                    <code className="font-mono text-[12.5px] text-slate-800">
                      {r.table}
                    </code>
                  </td>
                  <td className="px-5 py-2.5 tabular-nums text-[#4B5A52]">
                    {formatFullNumber(r.sourceRows)}
                  </td>
                  <td className="px-5 py-2.5 tabular-nums text-[#4B5A52]">
                    {formatFullNumber(r.targetRows)}
                  </td>
                  <td className="px-5 py-2.5">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11.5px] font-semibold tabular-nums ${
                        r.ok ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-700'
                      }`}
                    >
                      {r.ok
                        ? '100%'
                        : `${(100 - Math.min(100, r.mismatchPct)).toFixed(2)}%`}
                    </span>
                  </td>
                  <td className="px-5 py-2.5 text-[12px] text-[#7C8A83]">
                    {r.fkOk === null
                      ? '—'
                      : r.fkOk
                        ? 'FKs intact'
                        : 'orphaned rows'}
                    {r.sampleHash
                      ? ` · ${r.sampleHash.matched}/${r.sampleHash.sampled} hashes`
                      : ''}
                  </td>
                  <td className="px-5 py-2.5">
                    {r.ok ? (
                      <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-green-700">
                        <CheckCircle2 size={14} />
                        Verified
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-red-700">
                        <AlertTriangle size={14} />
                        {r.mismatchPct.toFixed(2)}% off
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {/* ── Recommended actions when something is off ─────────────── */}
      {flagged.size > 0 ? (
        <div className="mx-6 mt-6 rounded-xl border border-amber-300 bg-amber-50/70 p-5">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-600" />
            <div>
              <h3 className="text-sm font-semibold text-amber-900">
                Recommended actions
              </h3>
              <p className="mt-0.5 text-[12.5px] text-amber-800/80">
                {flagged.size} table{flagged.size === 1 ? '' : 's'} flagged for manual
                review before you point production at the target.
              </p>
              <ul className="mt-3 space-y-2">
                {[...flagged].map((table) => {
                  const r = results.find((x) => x.table === table);
                  return (
                    <li key={table} className="flex items-start gap-2 text-[12.5px]">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                      <span className="text-amber-900">
                        <code className="rounded bg-amber-100 px-1.5 py-0.5 font-mono text-[12px]">
                          {table}
                        </code>{' '}
                        {r && !r.ok
                          ? `is ${r.mismatchPct.toFixed(2)}% short — re-run this table with resume, then re-validate.`
                          : 'was flagged by the auditor — check the log for the specific failed assertion.'}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </div>
      ) : null}

      {report.notes && report.notes.length > 0 ? (
        <div className="mx-6 mt-4 rounded-xl border border-[#E4EDE7] bg-[#F7FAF8] p-4">
          <h3 className="text-[12px] font-semibold uppercase tracking-wide text-[#7C8A83]">
            Auditor notes
          </h3>
          <ul className="mt-2 space-y-1">
            {report.notes.map((note) => (
              <li key={note} className="text-[12.5px] text-[#4B5A52]">
                {note}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* ── Actions ───────────────────────────────────────────────── */}
      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-[#E4EDE7] bg-[#F7FAF8] px-6 py-5">
        {onDownloadPdf ? (
          <button
            type="button"
            onClick={onDownloadPdf}
            disabled={downloading}
            className="flex items-center gap-2 rounded-xl bg-green-600 px-5 py-2.5 text-[13.5px] font-semibold text-white shadow-sm transition-colors hover:bg-green-700 disabled:opacity-60"
          >
            {downloading ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Download size={15} />
            )}
            Download PDF report
          </button>
        ) : null}
        {onShare ? (
          <button
            type="button"
            onClick={onShare}
            className="flex items-center gap-2 rounded-xl border border-[#E4EDE7] bg-white px-5 py-2.5 text-[13.5px] font-medium text-[#0F1B14] transition-colors hover:border-slate-300"
          >
            <Share2 size={15} />
            Share report
          </button>
        ) : null}
        {onMonitor ? (
          <button
            type="button"
            onClick={onMonitor}
            disabled={monitoring}
            className="group ml-auto flex items-center gap-2 rounded-xl px-4 py-2.5 text-[13px] font-medium text-[#4B5A52] transition-colors hover:text-green-700 disabled:opacity-60"
          >
            {monitoring ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Radar size={15} className="text-green-600" />
            )}
            <span>
              Set up drift monitoring
              <span className="ml-1.5 rounded-full bg-green-100 px-2 py-0.5 text-[11px] font-semibold text-green-800">
                $49/mo
              </span>
            </span>
          </button>
        ) : null}
      </div>
    </section>
  );
}

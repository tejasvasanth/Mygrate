import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Filter,
  Loader2,
  ShieldCheck,
} from 'lucide-react';
import type { PreviewDiff as PreviewDiffData, PreviewDiffRow } from '@/types';

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

const TH =
  'sticky top-0 z-10 bg-[#F7FAF8] px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-[#7C8A83] shadow-[inset_0_-1px_0_#E4EDE7]';

/**
 * The core demo moment: the left half is what the schema declares, the right
 * half is what sampling the actual rows revealed. Rows that disagree are red,
 * and the approval gate below cannot be cleared until they are acknowledged.
 */
export function PreviewDiff({
  diff,
  acknowledged,
  onAcknowledge,
  onApprove,
  approving,
}: {
  diff: PreviewDiffData;
  /** When provided, renders the acknowledgement gate that unlocks approval. */
  acknowledged?: boolean;
  onAcknowledge?: (value: boolean) => void;
  /** When provided, the gate renders its own Approve button. */
  onApprove?: () => void;
  approving?: boolean;
}) {
  const [onlyMismatches, setOnlyMismatches] = useState(false);

  const gated = onAcknowledge !== undefined && diff.differing_count > 0;
  const tableCount = useMemo(
    () => new Set(diff.rows.filter((r) => r.differs).map((r) => r.table)).size,
    [diff.rows],
  );
  const rows = onlyMismatches ? diff.rows.filter((r) => r.differs) : diff.rows;

  return (
    <section className="overflow-hidden rounded-2xl border border-[#E4EDE7] bg-white shadow-sm">
      {/* ── Summary bar ───────────────────────────────────────────── */}
      <div
        className={`flex flex-wrap items-center justify-between gap-3 border-b px-6 py-4 ${
          diff.differing_count > 0
            ? 'border-amber-200 bg-amber-50/70'
            : 'border-[#E4EDE7] bg-green-50/60'
        }`}
      >
        <div className="flex items-start gap-3">
          {diff.differing_count > 0 ? (
            <AlertTriangle size={20} className="mt-0.5 shrink-0 text-amber-600" />
          ) : (
            <ShieldCheck size={20} className="mt-0.5 shrink-0 text-green-600" />
          )}
          <div>
            <h2 className="text-[15px] font-semibold text-[#0F1B14]">
              {diff.differing_count > 0
                ? `${diff.differing_count} mismatch${
                    diff.differing_count === 1 ? '' : 'es'
                  } found across ${tableCount} table${tableCount === 1 ? '' : 's'} — review before approving`
                : 'Schema and data agree on every column'}
            </h2>
            <p className="mt-0.5 text-[12.5px] text-[#4B5A52]">
              {diff.total_count.toLocaleString()} columns compared. Migrate will follow
              the recommendation column when it builds the target schema.
            </p>
          </div>
        </div>
        {diff.differing_count > 0 ? (
          <button
            type="button"
            onClick={() => setOnlyMismatches((v) => !v)}
            className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[12.5px] font-medium transition-colors ${
              onlyMismatches
                ? 'border-amber-400 bg-amber-100 text-amber-800'
                : 'border-[#E4EDE7] bg-white text-[#4B5A52] hover:border-slate-300'
            }`}
          >
            <Filter size={14} />
            {onlyMismatches ? 'Showing mismatches only' : 'Show mismatches only'}
          </button>
        ) : null}
      </div>

      {/* ── The diff table ────────────────────────────────────────── */}
      <div className="max-h-[560px] overflow-auto">
        <table className="w-full min-w-[1040px] border-collapse text-left text-[13px]">
          <thead>
            <tr>
              <th className={TH}>Column</th>
              <th className={TH}>Table</th>
              <th className={TH}>Declared type</th>
              <th className={TH}>Nullable</th>
              <th className={`${TH} w-px border-l border-[#E4EDE7] px-2`} aria-hidden />
              <th className={`${TH} text-green-700`}>Migrate infers</th>
              <th className={TH}>Recommendation</th>
              <th className={TH}>Confidence</th>
              <th className={TH}>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r: PreviewDiffRow) => (
              <tr
                key={`${r.table}.${r.column}`}
                className={`border-t border-[#E4EDE7] ${
                  r.differs ? 'bg-red-50/60' : 'hover:bg-slate-50/70'
                }`}
              >
                <td className="px-4 py-2.5">
                  <code
                    className={`font-mono text-[12.5px] ${
                      r.differs ? 'font-semibold text-red-800' : 'text-slate-800'
                    }`}
                  >
                    {r.column}
                  </code>
                </td>
                <td className="px-4 py-2.5 text-[12.5px] text-[#7C8A83]">{r.table}</td>
                <td className="px-4 py-2.5">
                  <span
                    className={`rounded px-1.5 py-0.5 font-mono text-[11.5px] ${
                      r.differs
                        ? 'bg-red-100 text-red-800 line-through decoration-red-400'
                        : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {r.declared.type ?? 'unknown'}
                  </span>
                  {r.declared.primary_key ? (
                    <span className="ml-1.5 text-[10px] font-semibold uppercase tracking-wide text-[#7C8A83]">
                      PK
                    </span>
                  ) : null}
                </td>
                <td className="px-4 py-2.5 text-[12px] text-[#7C8A83]">
                  {r.declared.nullable === false ? 'NOT NULL' : 'NULLABLE'}
                </td>
                <td className="w-px border-l border-[#E4EDE7] p-0" aria-hidden />
                <td className="px-4 py-2.5">
                  <span className="inline-flex items-center gap-1.5">
                    <ArrowRight size={12} className="text-green-600" />
                    <span className="rounded bg-green-100 px-1.5 py-0.5 font-mono text-[11.5px] font-semibold text-green-800">
                      {r.inferred.semantic_type}
                    </span>
                  </span>
                  {r.inferred.not_null_in_practice ? (
                    <span className="ml-1.5 text-[10px] font-semibold uppercase tracking-wide text-green-700">
                      not null in practice
                    </span>
                  ) : null}
                  {r.inferred.notes.length > 0 ? (
                    <div className="mt-0.5 text-[11.5px] leading-snug text-[#7C8A83]">
                      {r.inferred.notes.join(' · ')}
                    </div>
                  ) : null}
                </td>
                <td
                  className={`px-4 py-2.5 text-[12.5px] ${
                    r.differs ? 'font-medium text-red-800' : 'text-[#4B5A52]'
                  }`}
                >
                  {r.recommendation}
                </td>
                <td className="px-4 py-2.5">
                  <ConfidencePill value={r.confidence} />
                </td>
                <td className="px-4 py-2.5">
                  {r.differs ? (
                    <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-red-700">
                      <AlertTriangle size={14} />
                      Mismatch
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-[12px] text-green-700">
                      <CheckCircle2 size={14} />
                      Match
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-[13px] text-[#7C8A83]">
                  No columns to show.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {/* ── Approval gate ─────────────────────────────────────────── */}
      {gated ? (
        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-[#E4EDE7] bg-[#F7FAF8] px-6 py-5">
          <label className="flex cursor-pointer items-start gap-3 select-none">
            <input
              type="checkbox"
              checked={Boolean(acknowledged)}
              onChange={(e) => onAcknowledge?.(e.target.checked)}
              className="mt-0.5 shrink-0 cursor-pointer accent-green-600"
              style={{ width: 18, height: 18 }}
            />
            <span>
              <span className="block text-[13.5px] font-semibold text-[#0F1B14]">
                I have reviewed all {diff.differing_count} mismatch
                {diff.differing_count === 1 ? '' : 'es'}
              </span>
              <span className="mt-0.5 block text-[12px] text-[#7C8A83]">
                Nothing has been written to your target database yet.
              </span>
            </span>
          </label>

          {onApprove ? (
            <button
              type="button"
              disabled={!acknowledged || approving}
              onClick={onApprove}
              className={`flex items-center gap-2 rounded-xl px-6 py-3 text-[14px] font-semibold transition-all ${
                acknowledged && !approving
                  ? 'bg-green-600 text-white shadow-sm hover:bg-green-700 active:scale-[0.99]'
                  : 'cursor-not-allowed bg-slate-200 text-slate-400'
              }`}
            >
              {approving ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <CheckCircle2 size={16} />
              )}
              Approve &amp; execute migration
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

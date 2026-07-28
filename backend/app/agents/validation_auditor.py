"""Agent 5 — Validation Auditor: always runs, verifies the migration."""
from __future__ import annotations

import hashlib
import json
import random
from decimal import Decimal
from typing import Any

from ..connectors.base import BaseConnector
from ..utils.logger import job_logger

AGENT_NAME = "validation_auditor"
ROW_COUNT_MISMATCH_THRESHOLD = 0.001  # 0.1%
SAMPLE_HASH_ROWS = 50


class ValidationAuditor:
    def __init__(self, source: BaseConnector, target: BaseConnector,
                 plan: dict[str, Any], job_id: str, log_sink=None):
        self.source = source
        self.target = target
        self.plan = plan
        self.job_id = job_id
        self.log = job_logger(__name__, job_id, AGENT_NAME)
        self.log_sink = log_sink

    async def _emit(self, level: str, message: str, metadata: dict[str, Any] | None = None):
        self.log.info(message)
        if self.log_sink:
            await self.log_sink(level, AGENT_NAME, message, metadata or {})

    async def run(self) -> dict[str, Any]:
        await self._emit("info", "Starting post-migration validation…")
        tables_report: dict[str, Any] = {}
        flagged: list[str] = []
        scores: list[float] = []

        for spec in self.plan.get("tables", []):
            src = spec["source_table"]
            tgt = spec.get("target_table_name") or src
            mappings = spec.get("column_mappings", [])
            src_count = await self.source.count_rows(src)
            tgt_count = await self.target.count_rows(tgt)
            mismatch = abs(src_count - tgt_count) / src_count if src_count else (
                1.0 if tgt_count else 0.0)
            count_ok = mismatch <= ROW_COUNT_MISMATCH_THRESHOLD
            if not count_ok:
                flagged.append(src)

            hash_result = await self._sample_hash_check(src, tgt, mappings)
            fk_ok = await self._fk_check(src)
            tgt_fk_ok = await self._target_fk_check(src)
            fk_ok = fk_ok and tgt_fk_ok

            table_score = (
                (0.6 if count_ok else max(0.0, 0.6 * (1 - mismatch))) +
                0.3 * hash_result["match_ratio"] +
                (0.1 if fk_ok else 0.0)
            )
            scores.append(table_score)
            tables_report[src] = {
                "target_table": tgt,
                "source_rows": src_count,
                "target_rows": tgt_count,
                "row_count_ok": count_ok,
                "mismatch_pct": round(mismatch * 100, 3),
                "sample_hash": hash_result,
                "fk_integrity_ok": fk_ok,
            }
            level = "success" if count_ok else "warning"
            await self._emit(level,
                             f"'{src}': source={src_count} target={tgt_count} "
                             f"hash match={hash_result['match_ratio']:.0%}")

        confidence = round(100 * (sum(scores) / len(scores))) if scores else 0
        report = {
            "tables": tables_report,
            "flagged_tables": flagged,
            "confidence_score": confidence,
            "passed": not flagged and confidence >= 90,
        }
        await self._emit("success" if report["passed"] else "warning",
                         f"Validation complete. Confidence score: {confidence}%.",
                         {"flagged_tables": flagged})
        return report

    async def _single_pk_mapping(self, src: str,
                                 mappings: list[dict[str, Any]]) -> tuple[str, str] | None:
        """Returns (source_pk, target_pk) when the table has a single-column PK
        that is present in the column mappings."""
        schema = await self.source.get_schema()
        pk = schema["tables"].get(src, {}).get("primary_key") or []
        if len(pk) != 1:
            return None
        for m in mappings:
            if m["source_column"] == pk[0]:
                return pk[0], m["target_column"]
        return None

    async def _sample_hash_check(self, src: str, tgt: str,
                                 mappings: list[dict[str, Any]]) -> dict[str, Any]:
        """Hash-compare a random sample of rows column-by-column via the mapping.

        When the table has a usable primary key the target rows are fetched BY
        KEY, so the check stays correct on tables of any size. Only PK-less
        tables fall back to comparing against a bounded target sample."""
        src_rows = await self.source.sample_rows(src, 500)
        if not src_rows:
            return {"sampled": 0, "matched": 0, "match_ratio": 1.0}
        sample = random.sample(src_rows, min(SAMPLE_HASH_ROWS, len(src_rows)))

        pk_pair = await self._single_pk_mapping(src, mappings)
        if pk_pair:
            src_pk, tgt_pk = pk_pair
            keys = [r.get(src_pk) for r in sample if r.get(src_pk) is not None]
            tgt_rows = await self.target.fetch_rows_by_key(tgt, tgt_pk, keys)
            method = "by_primary_key"
        else:
            tgt_rows = await self.target.sample_rows(tgt, 5000)
            method = "sample_scan"
        tgt_hashes = {self._row_hash([r.get(m["target_column"]) for m in mappings])
                      for r in tgt_rows}
        matched = sum(
            1 for r in sample
            if self._row_hash([r.get(m["source_column"]) for m in mappings]) in tgt_hashes)
        return {"sampled": len(sample), "matched": matched,
                "match_ratio": round(matched / len(sample), 3), "method": method}

    @staticmethod
    def _row_hash(values: list[Any]) -> str:
        def norm(v: Any) -> str:
            if v is None:
                return ""
            if isinstance(v, bool):
                return "1" if v else "0"
            if hasattr(v, "isoformat"):  # datetime/date/time vs ISO text
                return v.isoformat()
            if isinstance(v, Decimal):  # Decimal('86.20') must equal float 86.2
                v = float(v)
            if isinstance(v, float) and v.is_integer():
                return str(int(v))
            if isinstance(v, (dict, list)):
                return json.dumps(v, sort_keys=True, default=str)
            return str(v)
        joined = "|".join(norm(v) for v in values)
        return hashlib.sha256(joined.encode()).hexdigest()

    async def _target_fk_check(self, table: str) -> bool:
        """Verify FK values actually resolve in the TARGET, mapped through the plan."""
        schema = await self.source.get_schema()
        fks = schema["tables"].get(table, {}).get("foreign_keys", [])
        if not fks:
            return True
        specs = {t["source_table"]: t for t in self.plan.get("tables", [])}
        spec = specs.get(table)
        if spec is None:
            return True

        def mapped(s: dict[str, Any], col: str) -> str | None:
            for m in s.get("column_mappings", []):
                if m["source_column"] == col:
                    return m["target_column"]
            return None

        tgt_table = spec.get("target_table_name") or table
        rows = await self.target.sample_rows(tgt_table, 200)
        for fk in fks:
            ref_spec = specs.get(fk["ref_table"])
            col = mapped(spec, fk["column"])
            if ref_spec is None or col is None:
                continue  # referenced table not migrated — nothing to verify
            ref_col = mapped(ref_spec, fk["ref_column"])
            if ref_col is None:
                continue
            ref_tgt = ref_spec.get("target_table_name") or fk["ref_table"]
            values = [r.get(col) for r in rows if r.get(col) is not None]
            if not values:
                continue
            resolved = {r.get(ref_col) for r in
                        await self.target.fetch_rows_by_key(ref_tgt, ref_col, values)}
            if any(v not in resolved for v in values):
                return False
        return True

    async def _fk_check(self, table: str) -> bool:
        """Verify FK values in source all resolve — a proxy for target integrity."""
        schema = await self.source.get_schema()
        fks = schema["tables"].get(table, {}).get("foreign_keys", [])
        if not fks:
            return True
        rows = await self.source.sample_rows(table, 200)
        for fk in fks:
            ref_rows = await self.source.sample_rows(fk["ref_table"], 5000)
            ref_values = {r.get(fk["ref_column"]) for r in ref_rows}
            for r in rows:
                v = r.get(fk["column"])
                if v is not None and ref_values and v not in ref_values:
                    return False
        return True

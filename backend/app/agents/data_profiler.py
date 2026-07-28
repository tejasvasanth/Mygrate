"""Agent 2 — Data Profiler: samples real rows and profiles what the data means."""
from __future__ import annotations

import re
from typing import Any

from ..connectors.base import BaseConnector
from ..utils.data_quality import build_data_quality_report
from ..utils.logger import job_logger
from ..utils.semantic_types import detect_implicit_foreign_keys, detect_semantic_type

AGENT_NAME = "data_profiler"
SAMPLE_LIMIT = 1000
ENUM_DISTINCT_THRESHOLD = 20

PII_PATTERNS = re.compile(
    r"(email|e_mail|phone|mobile|telephone|ssn|social_security|password|passwd|"
    r"secret|token|api_key|credit_card|card_number|cvv|iban|passport|"
    r"date_of_birth|dob|address|zip|postal)", re.IGNORECASE)

DATE_FORMATS = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "YYYY-MM-DD"),
    (re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}"), "ISO datetime"),
    (re.compile(r"^\d{2}/\d{2}/\d{4}$"), "MM/DD/YYYY or DD/MM/YYYY"),
    (re.compile(r"^\d{2}-\d{2}-\d{4}$"), "DD-MM-YYYY"),
    (re.compile(r"^\d{10,13}$"), "unix epoch"),
]


class DataProfiler:
    def __init__(self, source: BaseConnector, schema_snapshot: dict[str, Any],
                 job_id: str, log_sink=None, sample_limit: int = SAMPLE_LIMIT):
        self.source = source
        self.schema = schema_snapshot
        self.job_id = job_id
        self.sample_limit = sample_limit
        self.log = job_logger(__name__, job_id, AGENT_NAME)
        self.log_sink = log_sink

    async def _emit(self, level: str, message: str, metadata: dict[str, Any] | None = None):
        self.log.info(message)
        if self.log_sink:
            await self.log_sink(level, AGENT_NAME, message, metadata or {})

    async def run(self) -> dict[str, Any]:
        profile: dict[str, Any] = {"tables": {}}
        samples: dict[str, list[dict[str, Any]]] = {}
        for table in self.schema.get("tables", {}):
            await self._emit("info", f"Profiling table '{table}'…")
            rows = await self.source.sample_rows(table, self.sample_limit)
            samples[table] = rows
            profile["tables"][table] = self._profile_table(table, rows)

        # Relationship intelligence: undeclared FKs via cross-table matching.
        inferred_fks = detect_implicit_foreign_keys(
            self.schema.get("tables", {}), samples)
        profile["inferred_foreign_keys"] = inferred_fks
        for fk in inferred_fks:
            await self._emit(
                "warning",
                f"{fk['table']}.{fk['column']} matches {fk['likely_references']} "
                f"in {fk['match_pct']}% of sampled rows — likely undeclared FK.")

        # Data quality: what's broken in the source before it breaks the target.
        quality = build_data_quality_report(self.schema.get("tables", {}), samples)
        profile["quality"] = quality
        await self._emit(
            "warning" if quality["issues"] else "info",
            f"Data quality score {quality['quality_score']}/100 — "
            f"{len(quality['issues'])} issue(s) found.",
            {"counts": quality["counts"]})

        pii = [
            f"{t}.{c}" for t, tp in profile["tables"].items()
            for c, cp in tp["columns"].items() if cp["pii_suspected"]
        ]
        profile["summary"] = {"pii_fields": pii}
        await self._emit(
            "success",
            f"Data profiling complete. {len(pii)} suspected PII field(s) flagged.",
            {"pii_fields": pii},
        )
        return profile

    def _profile_table(self, table: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(rows)
        columns: dict[str, Any] = {}
        schema_cols = {c["name"]: c for c in
                       self.schema["tables"].get(table, {}).get("columns", [])}
        col_names = set(schema_cols)
        for r in rows:
            col_names.update(r.keys())
        for col in sorted(col_names):
            values = [r.get(col) for r in rows]
            non_null = [v for v in values if v is not None]
            distinct = set()
            for v in non_null:
                try:
                    distinct.add(v)
                except TypeError:  # unhashable (dict/list from mongo)
                    distinct.add(repr(v))
            null_pct = round(100 * (n - len(non_null)) / n, 1) if n else 0.0
            is_str = all(isinstance(v, str) for v in non_null) and bool(non_null)
            declared = schema_cols.get(col, {}).get("type")
            semantic = detect_semantic_type(col, declared, non_null)
            columns[col] = {
                "semantic": semantic,
                "null_pct": null_pct,
                "distinct_count": len(distinct),
                "implicit_boolean": self._implicit_bool(non_null),
                "implicit_enum": (
                    is_str and 0 < len(distinct) < ENUM_DISTINCT_THRESHOLD
                    and len(non_null) > len(distinct)
                ),
                "enum_values": (sorted(str(v) for v in distinct)
                                if is_str and len(distinct) < ENUM_DISTINCT_THRESHOLD else None),
                "pii_suspected": bool(PII_PATTERNS.search(col))
                or bool(semantic and semantic.get("pii")),
                "date_formats": self._date_formats(non_null) if is_str else [],
                "declared_type": declared,
                "sample_values": [repr(v) if isinstance(v, (dict, list)) else v
                                  for v in non_null[:5]],
            }
        return {"sampled_rows": n, "columns": columns}

    @staticmethod
    def _implicit_bool(values: list[Any]) -> bool:
        if not values:
            return False
        return all(v in (0, 1, "0", "1", True, False) for v in values)

    @staticmethod
    def _date_formats(values: list[Any]) -> list[str]:
        found: set[str] = set()
        for v in values[:200]:
            for pattern, label in DATE_FORMATS:
                if isinstance(v, str) and pattern.match(v):
                    found.add(label)
                    break
        return sorted(found)

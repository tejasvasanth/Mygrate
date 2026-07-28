"""Schema drift detection (T4-1) with semantic regression analysis (T4-3).

Diffs a live target schema against the baseline captured at migration time.
Severity follows data-loss risk, not novelty: an engineer paged at 3am should
only ever be paged for something that can lose or corrupt data.
"""
from __future__ import annotations

import re
from typing import Any

CRITICAL, WARNING, INFO = "critical", "warning", "info"

SEVERITY_RANK = {CRITICAL: 0, WARNING: 1, INFO: 2}

# Type changes that can silently truncate or lose precision.
NARROWING = [
    (re.compile(r"BIGINT", re.I), re.compile(r"\b(INT|INTEGER|SMALLINT)\b", re.I)),
    (re.compile(r"\b(TEXT|VARCHAR)", re.I), re.compile(r"\b(CHAR|VARCHAR)\(\d", re.I)),
    (re.compile(r"\b(DECIMAL|NUMERIC)", re.I), re.compile(r"\b(FLOAT|REAL|DOUBLE)\b", re.I)),
    (re.compile(r"\b(TIMESTAMP|DATETIME)", re.I), re.compile(r"\bDATE\b", re.I)),
]

# Declared-type → likely semantic type, learned from what Migrate detects.
SEMANTIC_HINTS = [
    (re.compile(r"TINYINT\(1\)|^TINYINT$|^BIT$", re.I), "boolean",
     "BOOLEAN with a CHECK constraint"),
    (re.compile(r"\b(FLOAT|DOUBLE|REAL)\b", re.I), "currency",
     "DECIMAL/NUMERIC if this column holds money"),
    (re.compile(r"^(VARCHAR|CHAR)\(36\)$", re.I), "uuid", "a native UUID type"),
    (re.compile(r"\b(INT|BIGINT)\b", re.I), "unix_timestamp",
     "TIMESTAMPTZ if this column holds epoch seconds"),
]

NAME_HINTS = [
    (re.compile(r"^(is_|has_|can_|should_)", re.I), "boolean", "BOOLEAN"),
    (re.compile(r"(price|amount|cost|total|balance|salary)", re.I), "currency",
     "DECIMAL/NUMERIC"),
    (re.compile(r"(email|phone|ssn)", re.I), "pii",
     "PII handling — mask in logs and restrict access"),
]


def _columns(table: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["name"]: c for c in table.get("columns", [])}


def _is_narrowing(old_type: str, new_type: str) -> bool:
    for wide, narrow in NARROWING:
        if wide.search(old_type or "") and narrow.search(new_type or ""):
            return True
    return False


def _semantic_regression(column: str, declared_type: str) -> dict[str, Any] | None:
    """T4-3 — would this new column be a semantic mismatch if we migrated it?"""
    for pattern, semantic, advice in NAME_HINTS:
        if pattern.search(column):
            return {"likely_semantic_type": semantic, "recommendation": advice}
    for pattern, semantic, advice in SEMANTIC_HINTS:
        if pattern.search(declared_type or ""):
            return {"likely_semantic_type": semantic, "recommendation": advice}
    return None


def _event(severity: str, kind: str, table: str, column: str | None,
           detail: str, **extra: Any) -> dict[str, Any]:
    return {"severity": severity, "kind": kind, "table": table,
            "column": column, "detail": detail, **extra}


def diff_schemas(baseline: dict[str, Any],
                 current: dict[str, Any]) -> dict[str, Any]:
    """Returns {events: [...], counts: {...}, has_drift: bool}."""
    events: list[dict[str, Any]] = []
    base_tables = (baseline or {}).get("tables", {}) or {}
    cur_tables = (current or {}).get("tables", {}) or {}

    for table in sorted(set(base_tables) - set(cur_tables)):
        events.append(_event(CRITICAL, "table_dropped", table, None,
                             f"Table '{table}' existed at baseline and is gone."))
    for table in sorted(set(cur_tables) - set(base_tables)):
        events.append(_event(INFO, "table_added", table, None,
                             f"New table '{table}' appeared since baseline."))

    for table in sorted(set(base_tables) & set(cur_tables)):
        base_cols = _columns(base_tables[table])
        cur_cols = _columns(cur_tables[table])

        for col in sorted(set(base_cols) - set(cur_cols)):
            events.append(_event(
                CRITICAL, "column_dropped", table, col,
                f"Column '{col}' was dropped — any data it held is gone."))

        for col in sorted(set(cur_cols) - set(base_cols)):
            info = cur_cols[col]
            declared = info.get("type", "")
            nullable = info.get("nullable", True)
            has_default = info.get("default") is not None
            severity = WARNING if (not nullable and not has_default) else INFO
            detail = (f"New column '{col}' ({declared})"
                      + ("" if nullable or has_default
                         else " is NOT NULL with no default — inserts without "
                              "it will fail"))
            regression = _semantic_regression(col, declared)
            events.append(_event(severity, "column_added", table, col, detail,
                                 semantic_regression=regression))

        for col in sorted(set(base_cols) & set(cur_cols)):
            old, new = base_cols[col], cur_cols[col]
            old_t, new_t = old.get("type", ""), new.get("type", "")
            if (old_t or "").upper() != (new_t or "").upper():
                narrowing = _is_narrowing(old_t, new_t)
                events.append(_event(
                    CRITICAL if narrowing else WARNING, "type_changed",
                    table, col,
                    f"Type changed {old_t} → {new_t}"
                    + (" — narrowing conversion risks data loss"
                       if narrowing else ""),
                    old_type=old_t, new_type=new_t))
            if old.get("nullable") is False and new.get("nullable") is True:
                events.append(_event(
                    CRITICAL, "not_null_dropped", table, col,
                    f"NOT NULL constraint dropped on '{col}' — nulls can now "
                    f"enter a column your application assumes is always set."))
            elif old.get("nullable") is True and new.get("nullable") is False:
                events.append(_event(
                    WARNING, "not_null_added", table, col,
                    f"'{col}' became NOT NULL — existing null rows would block "
                    f"this change."))

        base_idx = {i["name"]: i for i in base_tables[table].get("indexes", [])}
        cur_idx = {i["name"]: i for i in cur_tables[table].get("indexes", [])}
        for name in sorted(set(base_idx) - set(cur_idx)):
            events.append(_event(
                WARNING, "index_dropped", table, None,
                f"Index '{name}' was dropped — queries relying on it may "
                f"degrade" + (" and uniqueness is no longer enforced"
                              if base_idx[name].get("unique") else "")))
        for name in sorted(set(cur_idx) - set(base_idx)):
            events.append(_event(INFO, "index_added", table, None,
                                 f"New index '{name}' added."))

    events.sort(key=lambda e: (SEVERITY_RANK[e["severity"]], e["table"],
                               e["column"] or ""))
    counts = {sev: sum(1 for e in events if e["severity"] == sev)
              for sev in (CRITICAL, WARNING, INFO)}
    return {"events": events, "counts": counts, "has_drift": bool(events)}


def health_score(drift: dict[str, Any]) -> int:
    """0–100. Critical drift dominates; info events are free."""
    c = drift.get("counts", {})
    penalty = 25 * c.get(CRITICAL, 0) + 8 * c.get(WARNING, 0)
    return max(0, 100 - penalty)


def snapshot_for_baseline(schema: dict[str, Any]) -> dict[str, Any]:
    """Strip volatile fields (row counts) so drift means *structural* drift."""
    tables = {}
    for name, info in (schema or {}).get("tables", {}).items():
        tables[name] = {
            "columns": [{k: v for k, v in c.items() if k != "row_count"}
                        for c in info.get("columns", [])],
            "primary_key": info.get("primary_key", []),
            "foreign_keys": info.get("foreign_keys", []),
            "indexes": info.get("indexes", []),
        }
    return {"tables": tables}

"""Data Quality Report — what's broken in the source BEFORE it breaks the
target. Pure sample-based checks; the profiler supplies schema + samples."""
from __future__ import annotations

from collections import Counter
from typing import Any

SENTINEL_DATES = {"0000-00-00", "0000-00-00 00:00:00", "1970-01-01",
                  "1970-01-01 00:00:00", "1900-01-01"}
SENTINEL_NUMBERS = {-1, 9999, 99999, -999}
SENTINEL_MIN_SHARE = 0.05  # a sentinel must be >=5% of values to be suspicious

SEVERITY_WEIGHT = {"high": 12, "medium": 6, "low": 2}


def _issue(severity: str, kind: str, table: str, column: str | None,
           detail: str) -> dict[str, Any]:
    return {"severity": severity, "kind": kind, "table": table,
            "column": column, "detail": detail}


def build_data_quality_report(
        schema_tables: dict[str, Any],
        samples: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Returns {issues: [...], per_table: {...}, quality_score: int}."""
    issues: list[dict[str, Any]] = []

    for table, info in schema_tables.items():
        rows = samples.get(table, [])
        if not rows:
            continue
        n = len(rows)
        cols = {c["name"]: c for c in info.get("columns", [])}

        # 1 — NOT NULL string columns holding empty strings instead of NULL
        for name, col in cols.items():
            if col.get("nullable"):
                continue
            empties = sum(1 for r in rows if r.get(name) == "")
            if empties:
                issues.append(_issue(
                    "medium", "empty_string_in_not_null", table, name,
                    f"{empties}/{n} sampled rows hold '' in NOT NULL column — "
                    f"probably means missing data"))

        # 2 — sentinel dates
        for name in cols:
            hits = Counter(str(r.get(name)) for r in rows
                           if str(r.get(name))[:19] in SENTINEL_DATES
                           or str(r.get(name))[:10] in SENTINEL_DATES)
            if hits:
                total = sum(hits.values())
                issues.append(_issue(
                    "medium", "sentinel_date", table, name,
                    f"{total}/{n} rows use sentinel date(s) "
                    f"{sorted(hits)[:3]} — likely 'unknown' markers"))

        # 3 — numeric sentinels (only when suspiciously frequent)
        for name in cols:
            values = [r.get(name) for r in rows
                      if isinstance(r.get(name), (int, float))
                      and not isinstance(r.get(name), bool)]
            if not values:
                continue
            counts = Counter(v for v in values if v in SENTINEL_NUMBERS)
            for sentinel, cnt in counts.items():
                if cnt / n >= SENTINEL_MIN_SHARE:
                    issues.append(_issue(
                        "low", "numeric_sentinel", table, name,
                        f"value {sentinel} appears in {cnt}/{n} rows — "
                        f"possibly means 'missing'"))

        # 4 — duplicates in UNIQUE-indexed columns
        for idx in info.get("indexes", []):
            if not idx.get("unique") or len(idx.get("columns", [])) != 1:
                continue
            col = idx["columns"][0]
            vals = [r.get(col) for r in rows if r.get(col) is not None]
            dupes = [v for v, c in Counter(map(str, vals)).items() if c > 1]
            if dupes:
                issues.append(_issue(
                    "high", "duplicate_in_unique", table, col,
                    f"{len(dupes)} duplicated value(s) in UNIQUE column "
                    f"(e.g. {dupes[:3]}) — target unique constraint will fail"))

    # 5 — orphaned rows / FK violations. Only checked when the parent sample
    # fully covers the parent table (otherwise subset misses are meaningless).
    for table, info in schema_tables.items():
        rows = samples.get(table, [])
        for fk in info.get("foreign_keys", []):
            parent = fk["ref_table"]
            parent_info = schema_tables.get(parent, {})
            parent_rows = samples.get(parent, [])
            if not parent_rows or \
                    parent_info.get("row_count", 10**9) > len(parent_rows):
                continue
            parent_vals = {r.get(fk["ref_column"]) for r in parent_rows}
            orphans = [r.get(fk["column"]) for r in rows
                       if r.get(fk["column"]) is not None
                       and r.get(fk["column"]) not in parent_vals]
            if orphans:
                issues.append(_issue(
                    "high", "orphaned_rows", table, fk["column"],
                    f"{len(orphans)} sampled row(s) reference "
                    f"{parent}.{fk['ref_column']} values that do not exist "
                    f"(e.g. {sorted(set(map(str, orphans)))[:3]})"))

    penalty = sum(SEVERITY_WEIGHT.get(i["severity"], 2) for i in issues)
    score = max(0, 100 - penalty)
    per_table: dict[str, list[dict[str, Any]]] = {}
    for i in issues:
        per_table.setdefault(i["table"], []).append(i)
    return {
        "quality_score": score,
        "issues": issues,
        "per_table": per_table,
        "counts": dict(Counter(i["severity"] for i in issues)),
        "tables_checked": len([t for t in schema_tables if samples.get(t)]),
    }

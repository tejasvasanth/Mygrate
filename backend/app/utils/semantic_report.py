"""Semantic Mismatch Report Card — builds a structured report from the
Data Profiler output showing where declared schema and actual data disagree.

Pure functions only: consumes schema_snapshot + data_profile as stored on the
job, returns JSON-serializable dicts. No DB or network access.
"""
from __future__ import annotations

import re
from typing import Any

# Column-name → PII category. Order matters: first match wins.
PII_TYPES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"email|e_mail", re.I), "email"),
    (re.compile(r"phone|mobile|telephone", re.I), "phone"),
    (re.compile(r"ssn|social_security|passport|iban", re.I), "government_id"),
    (re.compile(r"password|passwd|secret|token|api_key", re.I), "credential"),
    (re.compile(r"credit_card|card_number|cvv", re.I), "payment"),
    (re.compile(r"date_of_birth|dob", re.I), "date_of_birth"),
    (re.compile(r"address|zip|postal", re.I), "address"),
    (re.compile(r"(first|last|full|middle)_?name|surname", re.I), "name"),
]


def _pii_type(column: str) -> str | None:
    for pattern, label in PII_TYPES:
        if pattern.search(column):
            return label
    return None


def _confidence(sampled: int, distinct: int, kind: str) -> int:
    """Heuristic confidence (0-100) that an inferred semantic type is real.
    Grows with sample size; enums additionally reward repetition."""
    if sampled <= 0:
        return 0
    size_conf = min(0.99, 0.5 + sampled / 2000)  # 500 rows → 0.75, 1000 → 0.99
    if kind == "enum" and distinct > 0:
        repetition = 1 - distinct / max(sampled, 1)
        return round(100 * min(0.99, size_conf * (0.6 + 0.4 * repetition)))
    return round(100 * size_conf)


def build_semantic_report(schema_snapshot: dict[str, Any],
                          data_profile: dict[str, Any]) -> dict[str, Any]:
    """Returns the Semantic Mismatch Report Card as a dict.

    Shape:
      { implicit_booleans: [...], implicit_enums: [...],
        never_null_nullables: [...], pii_columns: [...],
        summary: {...}, schema_trust_score: int }
    """
    booleans: list[dict[str, Any]] = []
    enums: list[dict[str, Any]] = []
    never_null: list[dict[str, Any]] = []
    pii: list[dict[str, Any]] = []
    semantic_detections: list[dict[str, Any]] = []
    dangerous: list[dict[str, Any]] = []
    total_columns = 0

    schema_tables = (schema_snapshot or {}).get("tables", {}) or {}
    for table, tprof in ((data_profile or {}).get("tables", {}) or {}).items():
        sampled = int(tprof.get("sampled_rows", 0))
        schema_cols = {c["name"]: c for c in
                       (schema_tables.get(table, {}) or {}).get("columns", [])}
        for col, cp in (tprof.get("columns", {}) or {}).items():
            total_columns += 1
            declared = cp.get("declared_type") or schema_cols.get(col, {}).get("type")
            loc = {"table": table, "column": col, "declared_type": declared,
                   "sample_size": sampled}

            declared_bool = bool(re.search(r"bool", str(declared or ""), re.I))
            if cp.get("implicit_boolean") and sampled > 0 and not declared_bool:
                booleans.append({**loc,
                                 "sample_values": (cp.get("enum_values") or ["0", "1"])[:4],
                                 "confidence": _confidence(sampled, 2, "boolean")})
            elif cp.get("implicit_enum"):
                enums.append({**loc,
                              "distinct_values": cp.get("enum_values") or [],
                              "distinct_count": cp.get("distinct_count", 0),
                              "confidence": _confidence(
                                  sampled, cp.get("distinct_count", 0), "enum")})

            nullable = schema_cols.get(col, {}).get("nullable")
            if nullable and sampled > 0 and cp.get("null_pct", 0) == 0:
                never_null.append(loc)

            sem = cp.get("semantic")
            if sem:
                entry = {**loc,
                         "inferred_semantic_type": sem["semantic_type"],
                         "confidence_pct": sem["confidence_pct"],
                         "sample_values": cp.get("sample_values", []),
                         "evidence_summary": sem["evidence_summary"]}
                semantic_detections.append(entry)
                if sem.get("danger"):
                    dangerous.append({**entry, "risk": sem["danger"]})

            if cp.get("pii_suspected"):
                pii.append({**loc, "pii_type": _pii_type(col)
                            or (sem or {}).get("semantic_type") or "other"})

    inferred_fks = (data_profile or {}).get("inferred_foreign_keys", []) or []
    mismatches = (len(booleans) + len(enums) + len(never_null)
                  + len(semantic_detections) + len(inferred_fks))

    # The score is driven by how many DISTINCT columns are untrustworthy, not
    # by how many findings there are. A column can appear in several buckets
    # (an implicit enum that is also never null); counting each finding would
    # let the penalty exceed the column count and peg every schema at zero.
    hard_columns: set[tuple[str, str]] = set()
    for finding in (*booleans, *enums, *semantic_detections):
        hard_columns.add((finding["table"], finding["column"]))
    soft_columns = {(n["table"], n["column"]) for n in never_null} - hard_columns

    if total_columns:
        # Never-null-but-nullable is advisory, so it weighs less than a type
        # the data contradicts outright.
        weighted_bad = len(hard_columns) + 0.35 * len(soft_columns)
        score = round(100 * (1 - min(1.0, weighted_bad / total_columns)))
        # Data-loss risks and undeclared relationships are extra deductions:
        # they are not just "a column to double-check".
        score -= 5 * len(dangerous) + 3 * len(inferred_fks) + 1 * len(pii)
        score = max(0, min(100, score))
    else:
        score = 0

    return {
        "implicit_booleans": booleans,
        "implicit_enums": enums,
        "never_null_nullables": never_null,
        "pii_columns": pii,
        "semantic_detections": semantic_detections,
        "dangerous_type_mismatches": dangerous,
        "implicit_foreign_keys": inferred_fks,
        "summary": {
            "total_columns_profiled": total_columns,
            "total_mismatches": mismatches,
            "implicit_boolean_count": len(booleans),
            "implicit_enum_count": len(enums),
            "never_null_nullable_count": len(never_null),
            "pii_column_count": len(pii),
            "semantic_detection_count": len(semantic_detections),
            "dangerous_mismatch_count": len(dangerous),
            "implicit_fk_count": len(inferred_fks),
        },
        "total_mismatches": mismatches,
        "schema_trust_score": score,
    }


def build_preview_diff(schema_snapshot: dict[str, Any],
                       data_profile: dict[str, Any],
                       migration_plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Side-by-side rows: what the schema declares vs what the data means.

    Each row: {table, column, declared: {...}, inferred: {...}, differs,
    confidence, recommendation}. `differs` marks any semantic disagreement.
    """
    report = build_semantic_report(schema_snapshot, data_profile)
    by_col: dict[tuple[str, str], dict[str, Any]] = {}
    for b in report["implicit_booleans"]:
        by_col[(b["table"], b["column"])] = {
            "semantic_type": "BOOLEAN",
            "note": f"only values {', '.join(b['sample_values'])} in "
                    f"{b['sample_size']} sampled rows",
            "confidence": b["confidence"]}
    for e in report["implicit_enums"]:
        by_col[(e["table"], e["column"])] = {
            "semantic_type": f"ENUM({e['distinct_count']} values)",
            "note": "distinct values: " + ", ".join(e["distinct_values"][:6]) +
                    ("…" if e["distinct_count"] > 6 else ""),
            "confidence": e["confidence"]}
    sem_advice = {
        "currency": "cast to DECIMAL — FLOAT loses cents",
        "zip_code": "keep as TEXT — never cast to INT",
        "uuid": "use native UUID type where the target has one",
        "unix_timestamp": "convert to TIMESTAMPTZ",
        "date_string": "convert to DATE/TIMESTAMP",
        "json_string": "use JSONB/JSON column type",
        "email": "mark as PII, add format validation",
        "phone": "mark as PII, add format validation",
        "url": "add format validation",
    }
    for d in report["semantic_detections"]:
        key = (d["table"], d["column"])
        if key in by_col:
            continue  # boolean/enum detection already claimed this column
        by_col[key] = {
            "semantic_type": d["inferred_semantic_type"].upper(),
            "note": d["evidence_summary"],
            "confidence": round(d["confidence_pct"]),
            "recommendation": sem_advice.get(d["inferred_semantic_type"]),
        }
    never_null = {(n["table"], n["column"]) for n in report["never_null_nullables"]}
    pii = {(p["table"], p["column"]): p["pii_type"] for p in report["pii_columns"]}

    plan_types: dict[tuple[str, str], str] = {}
    for spec in (migration_plan or {}).get("tables", []) or []:
        for m in spec.get("column_mappings", []) or []:
            plan_types[(spec.get("source_table", ""), m.get("source_column", ""))] = \
                m.get("target_type", "")

    rows: list[dict[str, Any]] = []
    schema_tables = (schema_snapshot or {}).get("tables", {}) or {}
    for table, tprof in ((data_profile or {}).get("tables", {}) or {}).items():
        sampled = int(tprof.get("sampled_rows", 0))
        schema_cols = {c["name"]: c for c in
                       (schema_tables.get(table, {}) or {}).get("columns", [])}
        for col, cp in (tprof.get("columns", {}) or {}).items():
            sc = schema_cols.get(col, {})
            key = (table, col)
            semantic = by_col.get(key)
            nn = key in never_null
            differs = bool(semantic) or nn
            inferred_type = (semantic or {}).get(
                "semantic_type", cp.get("declared_type") or sc.get("type") or "unknown")
            notes = []
            if semantic:
                notes.append(semantic["note"])
            if nn:
                notes.append(f"declared NULLABLE but 0 nulls in {sampled} rows")
            if key in pii:
                notes.append(f"suspected PII ({pii[key]})")
            recommendation = plan_types.get(key) or (
                (semantic or {}).get("recommendation")
                or (f"migrate as {inferred_type}" if differs else "keep as declared"))
            rows.append({
                "table": table,
                "column": col,
                "declared": {
                    "type": cp.get("declared_type") or sc.get("type"),
                    "nullable": sc.get("nullable"),
                    "primary_key": sc.get("primary_key", False),
                },
                "inferred": {
                    "semantic_type": inferred_type,
                    "not_null_in_practice": nn,
                    "pii_type": pii.get(key),
                    "notes": notes,
                },
                "recommendation": recommendation,
                "differs": differs,
                "confidence": (semantic or {}).get(
                    "confidence", _confidence(sampled, 0, "plain")),
            })
    rows.sort(key=lambda r: (not r["differs"], r["table"], r["column"]))
    return {
        "rows": rows,
        "differing_count": sum(1 for r in rows if r["differs"]),
        "total_count": len(rows),
        "schema_trust_score": report["schema_trust_score"],
    }


def build_confidence_breakdown(validation_report: dict[str, Any],
                               schema_snapshot: dict[str, Any],
                               data_profile: dict[str, Any],
                               review_threshold: int = 90) -> dict[str, Any]:
    """Per-table and per-column confidence, derived from the validation
    report's component scores plus semantic-mismatch penalties per column."""
    semantic = build_semantic_report(schema_snapshot, data_profile)
    mismatch_cols: dict[tuple[str, str], str] = {}
    for b in semantic["implicit_booleans"]:
        mismatch_cols[(b["table"], b["column"])] = "declared type hides a boolean"
    for e in semantic["implicit_enums"]:
        mismatch_cols[(e["table"], e["column"])] = "declared free text is an enum"
    pii_cols = {(p["table"], p["column"]): p["pii_type"]
                for p in semantic["pii_columns"]}

    tables_out: list[dict[str, Any]] = []
    flagged_columns: list[dict[str, Any]] = []
    for table, check in (validation_report.get("tables") or {}).items():
        hash_ratio = float((check.get("sample_hash") or {}).get("match_ratio", 1.0))
        mismatch = float(check.get("mismatch_pct", 0)) / 100
        table_conf = round(100 * (
            (0.6 if check.get("row_count_ok") else max(0.0, 0.6 * (1 - mismatch))) +
            0.3 * hash_ratio + (0.1 if check.get("fk_integrity_ok") else 0.0)))
        columns_out: list[dict[str, Any]] = []
        tprof = ((data_profile or {}).get("tables", {}) or {}).get(table, {})
        for col in (tprof.get("columns") or {}):
            reasons: list[str] = []
            conf = table_conf
            if (table, col) in mismatch_cols:
                conf -= 10
                reasons.append(mismatch_cols[(table, col)])
            if (table, col) in pii_cols:
                conf -= 5
                reasons.append(f"PII ({pii_cols[(table, col)]}) — verify handling")
            if hash_ratio < 1.0:
                reasons.append(f"sample hash match {hash_ratio:.0%} at table level")
            conf = max(0, min(100, conf))
            entry = {"column": col, "confidence": conf,
                     "needs_review": conf < review_threshold, "reasons": reasons}
            columns_out.append(entry)
            if entry["needs_review"]:
                flagged_columns.append({"table": table, **entry})
        columns_out.sort(key=lambda c: c["confidence"])
        tables_out.append({
            "table": table,
            "confidence": table_conf,
            "needs_review": table_conf < review_threshold,
            "components": {
                "row_count": check.get("row_count_ok", False),
                "sample_hash_ratio": hash_ratio,
                "fk_integrity": check.get("fk_integrity_ok", False),
            },
            "columns": columns_out,
        })
    tables_out.sort(key=lambda t: t["confidence"])
    return {
        "overall_confidence": validation_report.get("confidence_score", 0),
        "review_threshold": review_threshold,
        "tables": tables_out,
        "flagged_columns": flagged_columns,
    }

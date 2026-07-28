"""Extended semantic type detection — the core Migrate thesis.

Pure functions over sampled column values. Each detector returns
(semantic_type, confidence_pct, evidence_summary) or None. The profiler calls
`detect_semantic_type` per column and stores the result in the data profile.
"""
from __future__ import annotations

import json
import re
from typing import Any

MATCH_THRESHOLD = 0.95  # pattern detectors need >=95% of non-null values

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[\d\s().-]{7,20}$")
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?")
ZIP_RE = re.compile(r"^\d{4,10}$")
MONEY_NAME_RE = re.compile(
    r"(price|amount|cost|fee|total|balance|salary|revenue|charge|pay)", re.I)
ZIP_NAME_RE = re.compile(r"(zip|postal|pincode|pin_code)", re.I)

# Unix epoch seconds, 2000-01-01 .. 2038-01-19 (and ms variants of the same)
EPOCH_S = (946_684_800, 2_145_916_800)
EPOCH_MS = (EPOCH_S[0] * 1000, EPOCH_S[1] * 1000)


def _ratio(values: list[Any], pred) -> float:
    if not values:
        return 0.0
    return sum(1 for v in values if pred(v)) / len(values)


def _pct(ratio: float) -> float:
    return round(100 * ratio, 1)


def _is_intish(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def detect_semantic_type(column: str, declared_type: str | None,
                         values: list[Any]) -> dict[str, Any] | None:
    """Best single semantic-type detection for a column, or None.

    values must be the non-null sampled values. Returns
    {semantic_type, confidence_pct, evidence_summary, danger?, pii?}.
    """
    if not values:
        return None
    declared = (declared_type or "").upper()
    n = len(values)
    strings = [v for v in values if isinstance(v, str)]
    all_str = len(strings) == n

    # ── String-pattern detectors (>95% match) ────────────────────────────
    if all_str:
        for regex, sem, pii in [
            (EMAIL_RE, "email", True),
            (UUID_RE, "uuid", False),
            (URL_RE, "url", False),
        ]:
            r = _ratio(strings, regex.match)
            if r >= MATCH_THRESHOLD:
                return {"semantic_type": sem, "confidence_pct": _pct(r),
                        "pii": pii,
                        "evidence_summary": f"{_pct(r)}% of {n} sampled values "
                                            f"match the {sem} format"}
        # ISO dates are checked before phone: "2026-01-15" is digits-and-dashes
        # and would otherwise satisfy the looser phone pattern.
        r = _ratio(strings, ISO_DATE_RE.match)
        if r >= MATCH_THRESHOLD:
            return {"semantic_type": "date_string", "confidence_pct": _pct(r),
                    "evidence_summary": f"{_pct(r)}% of {n} sampled values are "
                                        f"ISO-format date strings stored as text"}
        # phone needs a digit-heavy guard — PHONE_RE alone matches plain numbers
        r = _ratio(strings, lambda s: bool(PHONE_RE.match(s))
                   and sum(c.isdigit() for c in s) >= 7 and not s.isdigit())
        if r >= MATCH_THRESHOLD:
            return {"semantic_type": "phone", "confidence_pct": _pct(r),
                    "pii": True,
                    "evidence_summary": f"{_pct(r)}% of {n} sampled values "
                                        f"look like phone numbers"}
        # zip/postal: all digits with leading zeros present, or named zip
        r = _ratio(strings, ZIP_RE.match)
        if r >= MATCH_THRESHOLD and (
                any(s.startswith("0") for s in strings) or ZIP_NAME_RE.search(column)):
            return {"semantic_type": "zip_code", "confidence_pct": _pct(r),
                    "danger": "casting to INT loses leading zeros",
                    "evidence_summary": f"{_pct(r)}% all-digit values"
                                        + (", leading zeros present"
                                           if any(s.startswith('0') for s in strings)
                                           else ", column name suggests postal code")}
        def _is_json(s: str) -> bool:
            s = s.strip()
            if not (s.startswith("{") or s.startswith("[")):
                return False
            try:
                json.loads(s)
                return True
            except (ValueError, TypeError):
                return False
        r = _ratio(strings, _is_json)
        if r >= MATCH_THRESHOLD:
            return {"semantic_type": "json_string", "confidence_pct": _pct(r),
                    "evidence_summary": f"{_pct(r)}% of {n} sampled values parse "
                                        f"as JSON"}

    # ── Numeric detectors ─────────────────────────────────────────────────
    ints = [v for v in values if _is_intish(v)]
    if len(ints) == n and n > 0:
        for lo, hi, unit in [(EPOCH_S[0], EPOCH_S[1], "seconds"),
                             (EPOCH_MS[0], EPOCH_MS[1], "milliseconds")]:
            r = _ratio(ints, lambda v: lo <= v <= hi)  # noqa: B023
            if r >= MATCH_THRESHOLD:
                return {"semantic_type": "unix_timestamp",
                        "confidence_pct": _pct(r),
                        "evidence_summary": f"{_pct(r)}% of values fall in the "
                                            f"Unix epoch range ({unit}, "
                                            f"2000–2038)"}
        if ZIP_NAME_RE.search(column):
            return {"semantic_type": "zip_code", "confidence_pct": 90.0,
                    "danger": "stored as INT — leading zeros already lost",
                    "evidence_summary": "integer column named like a postal "
                                        "code; leading zeros cannot survive"}

    floats = [v for v in values if isinstance(v, float)]
    if floats and any(t in declared for t in ("FLOAT", "DOUBLE", "REAL")):
        def _max2dp(v: Any) -> bool:
            try:
                return round(float(v), 2) == float(v)
            except (ValueError, TypeError, OverflowError):
                return False
        r = _ratio(values, _max2dp)
        named_money = bool(MONEY_NAME_RE.search(column))
        if r >= MATCH_THRESHOLD and (named_money or any(
                isinstance(v, float) and round(v, 2) == v and v != int(v)
                for v in values)):
            return {"semantic_type": "currency", "confidence_pct": _pct(r),
                    "danger": "FLOAT cannot represent currency exactly — "
                              "use DECIMAL/NUMERIC in the target",
                    "evidence_summary": f"{_pct(r)}% of values have ≤2 decimal "
                                        f"places"
                                        + (", column name suggests money"
                                           if named_money else "")}
    return None


def detect_implicit_foreign_keys(
        schema_tables: dict[str, Any],
        samples: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Cross-table value matching: *_id columns with no declared FK whose
    sampled values are a subset of another table's sampled PK values."""
    # candidate referenced sets: single-column PKs, sampled values
    pk_values: dict[str, tuple[str, set[Any]]] = {}
    for table, info in schema_tables.items():
        pk = info.get("primary_key") or []
        if len(pk) == 1:
            vals = {r.get(pk[0]) for r in samples.get(table, [])} - {None}
            if vals:
                pk_values[table] = (pk[0], vals)

    results: list[dict[str, Any]] = []
    for table, info in schema_tables.items():
        declared_fk_cols = {fk["column"] for fk in info.get("foreign_keys", [])}
        for col in info.get("columns", []):
            name = col["name"]
            if not name.lower().endswith("_id") or name in declared_fk_cols:
                continue
            values = [r.get(name) for r in samples.get(table, [])
                      if r.get(name) is not None]
            if not values or not all(_is_intish(v) or isinstance(v, str)
                                     for v in values):
                continue
            best: dict[str, Any] | None = None
            stem = name.lower()[:-3]  # users_id/user_id -> user
            for ref_table, (ref_col, ref_vals) in pk_values.items():
                if ref_table == table:
                    continue
                match = _ratio(values, lambda v: v in ref_vals)  # noqa: B023
                if match < MATCH_THRESHOLD:
                    continue
                name_bonus = (ref_table.lower().rstrip("s") == stem.rstrip("s"))
                cand = {"table": table, "column": name,
                        "likely_references": f"{ref_table}.{ref_col}",
                        "match_pct": _pct(match), "name_match": name_bonus}
                if best is None or (cand["name_match"] and not best["name_match"]) \
                        or cand["match_pct"] > best["match_pct"]:
                    best = cand
            if best:
                results.append(best)
    return results

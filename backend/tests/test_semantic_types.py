"""Tests for the extended semantic type library (T1-1) and relationship
intelligence (T1-4)."""
import uuid

from app.utils.semantic_types import (
    detect_implicit_foreign_keys,
    detect_semantic_type,
)


def _sem(column, declared, values):
    return detect_semantic_type(column, declared, values)


def test_email_detection():
    values = [f"user{i}@example.com" for i in range(100)]
    r = _sem("contact", "VARCHAR(255)", values)
    assert r["semantic_type"] == "email"
    assert r["confidence_pct"] == 100.0
    assert r["pii"] is True


def test_email_below_threshold_not_detected():
    values = [f"user{i}@example.com" for i in range(90)] + ["garbage"] * 10
    assert _sem("contact", "VARCHAR(255)", values) is None


def test_uuid_detection():
    values = [str(uuid.uuid4()) for _ in range(50)]
    r = _sem("external_ref", "CHAR(36)", values)
    assert r["semantic_type"] == "uuid"


def test_url_detection():
    values = [f"https://example.com/page/{i}" for i in range(40)]
    assert _sem("website", "TEXT", values)["semantic_type"] == "url"


def test_phone_detection_and_plain_digits_are_not_phones():
    phones = ["+1 (555) 010-{:04d}".format(i) for i in range(40)]
    assert _sem("mobile", "VARCHAR(32)", phones)["semantic_type"] == "phone"
    # a bare digit string is a zip/other, never a phone
    plain = [f"{i:07d}" for i in range(40)]
    r = _sem("code", "VARCHAR(16)", plain)
    assert r is None or r["semantic_type"] != "phone"


def test_unix_timestamp_detection():
    values = [1_700_000_000 + i for i in range(50)]
    r = _sem("created", "BIGINT", values)
    assert r["semantic_type"] == "unix_timestamp"
    # ordinary small ints are not timestamps
    assert _sem("qty", "INT", list(range(50))) is None


def test_currency_flagged_as_dangerous():
    values = [round(9.99 + i * 0.5, 2) for i in range(60)]
    r = _sem("price", "FLOAT", values)
    assert r["semantic_type"] == "currency"
    assert "DECIMAL" in r["danger"]


def test_zip_code_with_leading_zeros():
    values = ["02134"] * 20 + ["10001"] * 20
    r = _sem("postal", "VARCHAR(10)", values)
    assert r["semantic_type"] == "zip_code"
    assert "leading zeros" in r["danger"]


def test_zip_code_declared_as_int_is_dangerous():
    r = _sem("zip_code", "INT", [10001, 94105, 60601] * 10)
    assert r["semantic_type"] == "zip_code"
    assert "leading zeros" in r["danger"]


def test_iso_date_string_detection():
    values = [f"2026-0{(i % 9) + 1}-15" for i in range(40)]
    assert _sem("due", "VARCHAR(32)", values)["semantic_type"] == "date_string"


def test_json_string_detection():
    values = ['{"a": %d}' % i for i in range(40)]
    assert _sem("payload", "TEXT", values)["semantic_type"] == "json_string"


def test_no_detection_on_free_text():
    values = [f"some free text number {i}" for i in range(50)]
    assert _sem("notes", "TEXT", values) is None


def test_empty_values_return_none():
    assert _sem("anything", "TEXT", []) is None


SCHEMA_TABLES = {
    "users": {
        "columns": [{"name": "id", "type": "INT", "nullable": False}],
        "primary_key": ["id"], "foreign_keys": [], "row_count": 3,
    },
    "orders": {
        "columns": [{"name": "id", "type": "INT", "nullable": False},
                    {"name": "user_id", "type": "INT", "nullable": True},
                    {"name": "ghost_id", "type": "INT", "nullable": True}],
        "primary_key": ["id"], "foreign_keys": [], "row_count": 3,
    },
}


def test_implicit_fk_detected_by_value_matching():
    samples = {
        "users": [{"id": 1}, {"id": 2}, {"id": 3}],
        "orders": [{"id": 10, "user_id": 1, "ghost_id": 777},
                   {"id": 11, "user_id": 2, "ghost_id": 888},
                   {"id": 12, "user_id": 3, "ghost_id": 999}],
    }
    fks = detect_implicit_foreign_keys(SCHEMA_TABLES, samples)
    by_col = {f["column"]: f for f in fks}
    assert by_col["user_id"]["likely_references"] == "users.id"
    assert by_col["user_id"]["match_pct"] == 100.0
    # ghost_id values match nothing — must not be reported
    assert "ghost_id" not in by_col


def test_declared_fk_is_not_reported_as_implicit():
    schema = {**SCHEMA_TABLES}
    schema["orders"] = {**SCHEMA_TABLES["orders"],
                        "foreign_keys": [{"column": "user_id",
                                          "ref_table": "users",
                                          "ref_column": "id"}]}
    samples = {"users": [{"id": 1}], "orders": [{"id": 10, "user_id": 1}]}
    assert detect_implicit_foreign_keys(schema, samples) == []

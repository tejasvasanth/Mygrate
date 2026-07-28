"""Unit tests for the Semantic Mismatch Report Card builder."""
from app.utils.compliance import build_compliance_matrix
from app.utils.semantic_report import (
    build_confidence_breakdown,
    build_preview_diff,
    build_semantic_report,
)

SCHEMA = {
    "tables": {
        "users": {
            "columns": [
                {"name": "id", "type": "INTEGER", "nullable": False, "primary_key": True},
                {"name": "is_active", "type": "TINYINT(1)", "nullable": True},
                {"name": "status", "type": "VARCHAR(50)", "nullable": True},
                {"name": "email", "type": "VARCHAR(255)", "nullable": True},
                {"name": "nickname", "type": "VARCHAR(50)", "nullable": True},
            ],
        }
    }
}

PROFILE = {
    "tables": {
        "users": {
            "sampled_rows": 1000,
            "columns": {
                "id": {"null_pct": 0.0, "distinct_count": 1000,
                       "implicit_boolean": False, "implicit_enum": False,
                       "enum_values": None, "pii_suspected": False,
                       "date_formats": [], "declared_type": "INTEGER"},
                "is_active": {"null_pct": 0.0, "distinct_count": 2,
                              "implicit_boolean": True, "implicit_enum": False,
                              "enum_values": ["0", "1"], "pii_suspected": False,
                              "date_formats": [], "declared_type": "TINYINT(1)"},
                "status": {"null_pct": 0.0, "distinct_count": 3,
                           "implicit_boolean": False, "implicit_enum": True,
                           "enum_values": ["active", "banned", "pending"],
                           "pii_suspected": False, "date_formats": [],
                           "declared_type": "VARCHAR(50)"},
                "email": {"null_pct": 2.0, "distinct_count": 980,
                          "implicit_boolean": False, "implicit_enum": False,
                          "enum_values": None, "pii_suspected": True,
                          "date_formats": [], "declared_type": "VARCHAR(255)"},
                "nickname": {"null_pct": 40.0, "distinct_count": 500,
                             "implicit_boolean": False, "implicit_enum": False,
                             "enum_values": None, "pii_suspected": False,
                             "date_formats": [], "declared_type": "VARCHAR(50)"},
            },
        }
    }
}


def test_detects_implicit_boolean():
    report = build_semantic_report(SCHEMA, PROFILE)
    assert report["summary"]["implicit_boolean_count"] == 1
    b = report["implicit_booleans"][0]
    assert b["column"] == "is_active"
    assert b["declared_type"] == "TINYINT(1)"
    assert b["confidence"] >= 90


def test_detects_implicit_enum():
    report = build_semantic_report(SCHEMA, PROFILE)
    assert report["summary"]["implicit_enum_count"] == 1
    e = report["implicit_enums"][0]
    assert e["column"] == "status"
    assert e["distinct_values"] == ["active", "banned", "pending"]
    assert e["confidence"] >= 80


def test_detects_never_null_nullable():
    report = build_semantic_report(SCHEMA, PROFILE)
    cols = {c["column"] for c in report["never_null_nullables"]}
    # is_active and status are nullable but 0% null; nickname has nulls; id is NOT NULL
    assert cols == {"is_active", "status"}


def test_pii_typed():
    report = build_semantic_report(SCHEMA, PROFILE)
    assert report["pii_columns"] == [{
        "table": "users", "column": "email", "declared_type": "VARCHAR(255)",
        "sample_size": 1000, "pii_type": "email"}]


def test_trust_score_in_range():
    report = build_semantic_report(SCHEMA, PROFILE)
    assert 0 <= report["schema_trust_score"] <= 100
    # 3 mismatches over 5 columns + 1 PII → noticeably below 100
    assert report["schema_trust_score"] < 60


def test_empty_inputs():
    report = build_semantic_report({}, {})
    assert report["schema_trust_score"] == 0
    assert report["summary"]["total_columns_profiled"] == 0


def test_preview_diff_marks_differing_rows_first():
    diff = build_preview_diff(SCHEMA, PROFILE)
    assert diff["total_count"] == 5
    # is_active (bool), status (enum + never-null) differ; email is PII-noted
    # but PII alone is not a schema mismatch
    differing = [r for r in diff["rows"] if r["differs"]]
    assert {(r["table"], r["column"]) for r in differing} == {
        ("users", "is_active"), ("users", "status")}
    # differing rows sort to the top
    assert all(r["differs"] for r in diff["rows"][:diff["differing_count"]])
    bool_row = next(r for r in diff["rows"] if r["column"] == "is_active")
    assert bool_row["inferred"]["semantic_type"] == "BOOLEAN"
    assert bool_row["declared"]["type"] == "TINYINT(1)"


def test_preview_diff_uses_plan_recommendation():
    plan = {"tables": [{"source_table": "users", "column_mappings": [
        {"source_column": "is_active", "target_column": "is_active",
         "target_type": "BOOLEAN"}]}]}
    diff = build_preview_diff(SCHEMA, PROFILE, plan)
    bool_row = next(r for r in diff["rows"] if r["column"] == "is_active")
    assert bool_row["recommendation"] == "BOOLEAN"


def test_confidence_breakdown_flags_below_threshold():
    validation = {"confidence_score": 92, "tables": {"users": {
        "target_table": "users", "source_rows": 1000, "target_rows": 1000,
        "row_count_ok": True, "mismatch_pct": 0.0, "fk_integrity_ok": True,
        "sample_hash": {"sampled": 50, "matched": 50, "match_ratio": 1.0}}}}
    bd = build_confidence_breakdown(validation, SCHEMA, PROFILE)
    users = bd["tables"][0]
    assert users["confidence"] == 100
    by_col = {c["column"]: c for c in users["columns"]}
    assert by_col["is_active"]["confidence"] == 90  # -10 semantic mismatch
    assert not by_col["is_active"]["needs_review"]
    assert by_col["email"]["confidence"] == 95  # -5 PII
    assert by_col["id"]["confidence"] == 100
    # imperfect hash pulls everything down and flags columns
    validation["tables"]["users"]["sample_hash"]["match_ratio"] = 0.8
    bd2 = build_confidence_breakdown(validation, SCHEMA, PROFILE)
    assert bd2["tables"][0]["confidence"] == 94
    # 94 base: semantic mismatches (-10) and PII (-5) columns drop under 90
    assert {c["column"] for c in bd2["flagged_columns"]} == {
        "is_active", "status", "email"}


def test_compliance_matrix_covers_all_families():
    matrix = build_compliance_matrix()
    families = {e["family"] for e in matrix["entries"]}
    assert families == {"postgres", "mysql", "mongodb", "sqlite",
                        "sqlserver", "bigquery", "dynamodb", "neo4j"}
    # core drivers are installed in this environment
    core = [e for e in matrix["entries"]
            if e["family"] in ("postgres", "mysql", "mongodb", "sqlite")]
    assert all(e["compliant"] for e in core)
    assert matrix["total_count"] == len(matrix["entries"])

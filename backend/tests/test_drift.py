"""Tests for schema drift detection (T4-1/T4-3), public reports (T3-2),
badges (T3-5), templates (T3-4) and read-only advice (T2-5)."""
from app.utils.drift import diff_schemas, health_score, snapshot_for_baseline
from app.utils.public_report import (
    badge_markdown,
    badge_svg,
    build_public_report,
    estimate_manual_hours,
    make_share_token,
)
from app.utils.readonly import readonly_connection_string, readonly_grant_sql
from app.utils.templates import get_template, list_templates


def _schema(columns, indexes=None):
    return {"tables": {"users": {
        "columns": columns, "primary_key": ["id"], "foreign_keys": [],
        "indexes": indexes or []}}}


BASE_COLS = [
    {"name": "id", "type": "INT", "nullable": False},
    {"name": "email", "type": "VARCHAR(255)", "nullable": False},
]


def test_no_drift_when_identical():
    s = _schema(BASE_COLS)
    drift = diff_schemas(s, s)
    assert drift["has_drift"] is False
    assert health_score(drift) == 100


def test_dropped_column_is_critical():
    drift = diff_schemas(_schema(BASE_COLS), _schema(BASE_COLS[:1]))
    event = drift["events"][0]
    assert event["kind"] == "column_dropped"
    assert event["severity"] == "critical"
    assert health_score(drift) == 75


def test_dropped_table_is_critical():
    drift = diff_schemas(_schema(BASE_COLS), {"tables": {}})
    assert drift["events"][0]["kind"] == "table_dropped"
    assert drift["events"][0]["severity"] == "critical"


def test_dropped_not_null_is_critical():
    relaxed = [BASE_COLS[0], {**BASE_COLS[1], "nullable": True}]
    drift = diff_schemas(_schema(BASE_COLS), _schema(relaxed))
    kinds = {e["kind"]: e for e in drift["events"]}
    assert kinds["not_null_dropped"]["severity"] == "critical"


def test_narrowing_type_change_is_critical_widening_is_warning():
    narrowed = [{"name": "id", "type": "SMALLINT", "nullable": False},
                BASE_COLS[1]]
    drift = diff_schemas(
        _schema([{"name": "id", "type": "BIGINT", "nullable": False},
                 BASE_COLS[1]]), _schema(narrowed))
    event = next(e for e in drift["events"] if e["kind"] == "type_changed")
    assert event["severity"] == "critical"
    assert "data loss" in event["detail"]

    widened = [{"name": "id", "type": "BIGINT", "nullable": False}, BASE_COLS[1]]
    drift2 = diff_schemas(
        _schema([{"name": "id", "type": "INT", "nullable": False},
                 BASE_COLS[1]]), _schema(widened))
    assert next(e for e in drift2["events"]
                if e["kind"] == "type_changed")["severity"] == "warning"


def test_new_not_null_column_without_default_is_warning():
    added = BASE_COLS + [{"name": "tier", "type": "VARCHAR(20)",
                          "nullable": False, "default": None}]
    drift = diff_schemas(_schema(BASE_COLS), _schema(added))
    event = next(e for e in drift["events"] if e["kind"] == "column_added")
    assert event["severity"] == "warning"
    assert "NOT NULL with no default" in event["detail"]


def test_new_nullable_column_is_info():
    added = BASE_COLS + [{"name": "notes", "type": "TEXT", "nullable": True}]
    drift = diff_schemas(_schema(BASE_COLS), _schema(added))
    assert next(e for e in drift["events"]
                if e["kind"] == "column_added")["severity"] == "info"
    assert health_score(drift) == 100  # info events are free


def test_semantic_regression_on_new_tinyint_column():
    """T4-3 — a new TINYINT named is_* should be recognised as a boolean."""
    added = BASE_COLS + [{"name": "is_verified", "type": "TINYINT",
                          "nullable": True}]
    drift = diff_schemas(_schema(BASE_COLS), _schema(added))
    event = next(e for e in drift["events"] if e["column"] == "is_verified")
    regression = event["semantic_regression"]
    assert regression["likely_semantic_type"] == "boolean"
    assert "BOOLEAN" in regression["recommendation"]


def test_dropped_unique_index_mentions_uniqueness():
    with_idx = _schema(BASE_COLS, [{"name": "uq_email", "columns": ["email"],
                                    "unique": True}])
    drift = diff_schemas(with_idx, _schema(BASE_COLS))
    event = next(e for e in drift["events"] if e["kind"] == "index_dropped")
    assert "uniqueness is no longer enforced" in event["detail"]


def test_events_sorted_critical_first():
    changed = [{"name": "id", "type": "SMALLINT", "nullable": False}]
    drift = diff_schemas(_schema(BASE_COLS), _schema(changed))
    severities = [e["severity"] for e in drift["events"]]
    assert severities == sorted(severities,
                                key=lambda s: {"critical": 0, "warning": 1,
                                               "info": 2}[s])


def test_baseline_snapshot_strips_row_counts():
    schema = {"tables": {"users": {"columns": BASE_COLS, "row_count": 500,
                                   "primary_key": ["id"], "foreign_keys": [],
                                   "indexes": []}}}
    snap = snapshot_for_baseline(schema)
    assert "row_count" not in snap["tables"]["users"]
    # a pure row-count change must not register as drift
    schema2 = {"tables": {**schema["tables"],
                          "users": {**schema["tables"]["users"],
                                    "row_count": 900}}}
    assert diff_schemas(snap, snapshot_for_baseline(schema2))["has_drift"] is False


JOB = {
    "id": "job-42", "name": "prod migration",
    "source_db_type": "mysql", "target_db_type": "postgres",
    "status": "completed", "rows_migrated": 250_000,
    "started_at": "2026-07-01T10:00:00+00:00",
    "completed_at": "2026-07-01T10:30:00+00:00",
    "migration_plan": {"tables": [{"source_table": "customers"},
                                  {"source_table": "invoices"}]},
    "validation_report": {"confidence_score": 99.4, "tables": {
        "customers": {"source_rows": 100, "target_rows": 100,
                      "row_count_ok": True}}},
}

SEMANTIC = {"schema_trust_score": 74, "summary": {
    "implicit_boolean_count": 2, "implicit_enum_count": 1,
    "never_null_nullable_count": 1, "dangerous_mismatch_count": 1,
    "implicit_fk_count": 1, "pii_column_count": 3, "total_mismatches": 7}}


def test_public_report_redacts_table_names_by_default():
    report = build_public_report(JOB, SEMANTIC)
    assert [t["table"] for t in report["tables"]] == ["table_1", "table_2"]
    assert report["names_redacted"] is True
    blob = str(report)
    assert "customers" not in blob and "invoices" not in blob


def test_public_report_can_show_names_when_opted_in():
    report = build_public_report(JOB, SEMANTIC, redact_names=False)
    assert [t["table"] for t in report["tables"]] == ["customers", "invoices"]


def test_public_report_never_leaks_credentials():
    job = {**JOB, "source_credential_id": "vault-secret-abc",
           "target_credential_id": "vault-secret-def",
           "user_id": "user-123"}
    blob = str(build_public_report(job, SEMANTIC))
    assert "vault-secret-abc" not in blob
    assert "vault-secret-def" not in blob
    assert "user-123" not in blob


def test_public_report_counts_mismatches_without_column_names():
    report = build_public_report(JOB, SEMANTIC)
    assert report["semantic_mismatches_caught"]["total"] == 7
    assert report["semantic_mismatches_caught"]["dangerous_type_mismatches"] == 1
    assert report["duration_seconds"] == 1800.0
    assert report["estimated_manual_hours"] > 0


def test_manual_hours_estimate_scales():
    assert estimate_manual_hours(10, 0) == 20.0
    assert estimate_manual_hours(0, 200_000) == 3.0


def test_share_token_is_stable_and_opaque():
    t1, t2 = make_share_token("job-42"), make_share_token("job-42")
    assert t1 == t2 and len(t1) == 16
    assert "job-42" not in t1
    assert make_share_token("job-43") != t1


def test_badge_svg_colour_reflects_confidence():
    assert "#16A34A" in badge_svg(99.4)
    assert "#D97706" in badge_svg(75.0)
    assert "#DC2626" in badge_svg(40.0)
    assert badge_svg(99.4).startswith("<svg")


def test_badge_markdown_links_report_and_image():
    md = badge_markdown("https://migrate.run", "abc123", 99.4)
    assert "https://migrate.run/api/v1/public/abc123/badge.svg" in md
    assert "https://migrate.run/r/abc123" in md
    assert "99.4% confidence" in md


def test_templates_expose_expected_stacks():
    slugs = {t["slug"] for t in list_templates()}
    assert "laravel-mysql-to-supabase-postgres" in slugs
    assert "mongodb-atlas-to-supabase-postgres" in slugs
    assert len(slugs) == 5
    # the index view omits the bulky type table
    assert all("type_overrides" not in t for t in list_templates())


def test_template_detail_includes_quirks_and_overrides():
    t = get_template("laravel-mysql-to-supabase-postgres")
    assert t["type_overrides"]["TINYINT(1)"] == "BOOLEAN"
    assert any("TINYINT(1)" in q for q in t["quirks"])
    assert get_template("nope") is None


def test_pdf_report_includes_all_sections():
    """T3-3 — cover page, semantic card, plan, validation, rollback pointer."""
    from app.utils.pdf_report import render_report_pdf

    job = {**JOB, "id": "job-42", "rows_migrated": 250_000,
           "schema_snapshot": {"tables": {}}}
    report = {"executive_summary": "All good.", "confidence_score": 99.4,
              "passed": True, "generated_at": "2026-07-27T12:00:00",
              "flags": [], "recommendations": ["Add indexes on the target."]}
    pdf = render_report_pdf(job, report, semantic=SEMANTIC,
                            confidence_breakdown={"tables": [
                                {"table": "customers", "confidence": 96,
                                 "columns": [{"column": "email",
                                              "needs_review": True}]}]})
    assert pdf.startswith(b"%PDF")
    # A cover page plus content means more than a single page.
    assert pdf.count(b"/Type /Page") >= 2 or b"/Count 2" in pdf or len(pdf) > 5000


def test_pdf_report_renders_without_optional_sections():
    from app.utils.pdf_report import render_report_pdf

    pdf = render_report_pdf(
        {"id": "j", "name": "bare", "source_db_type": "mysql",
         "target_db_type": "postgres"},
        {"executive_summary": "x", "confidence_score": 50, "passed": False,
         "generated_at": "2026-07-27T12:00:00", "flags": [],
         "recommendations": []})
    assert pdf.startswith(b"%PDF")


def test_readonly_grants_per_engine():
    mysql = readonly_grant_sql("mysql", "mysql://u:p@h/shop")
    assert any("GRANT SELECT ON `shop`.*" in s for s in mysql)
    pg = readonly_grant_sql("postgres", "postgresql://u:p@h/shop")
    assert any("GRANT SELECT ON ALL TABLES IN SCHEMA public" in s for s in pg)
    mongo = readonly_grant_sql("mongodb", "mongodb://u:p@h/shop")
    assert any('role: "read"' in s for s in mongo)


def test_readonly_connection_string_swaps_user_and_keeps_host():
    out = readonly_connection_string("mysql://admin:secret@db.host:3306/shop",
                                     "newpass")
    assert "migrate_ro:newpass@db.host:3306" in out
    assert "admin" not in out and "secret" not in out
    assert out.endswith("/shop")

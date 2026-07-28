"""Tests for the Data Quality Report (T1-5), rollback scripts (T2-2) and
simulation (T2-1)."""
from app.utils.data_quality import build_data_quality_report
from app.utils.rollback import generate_rollback_script
from app.utils.simulate import simulate_table

SCHEMA = {
    "users": {
        "columns": [{"name": "id", "type": "INT", "nullable": False},
                    {"name": "email", "type": "VARCHAR(255)", "nullable": False},
                    {"name": "age", "type": "INT", "nullable": True},
                    {"name": "joined", "type": "VARCHAR(32)", "nullable": True}],
        "primary_key": ["id"],
        "foreign_keys": [],
        "indexes": [{"name": "uq_email", "columns": ["email"], "unique": True}],
        "row_count": 4,
    },
    "orders": {
        "columns": [{"name": "id", "type": "INT", "nullable": False},
                    {"name": "user_id", "type": "INT", "nullable": True}],
        "primary_key": ["id"],
        "foreign_keys": [{"column": "user_id", "ref_table": "users",
                          "ref_column": "id"}],
        "indexes": [],
        "row_count": 3,
    },
}

SAMPLES = {
    "users": [
        {"id": 1, "email": "a@x.com", "age": 30, "joined": "2020-01-01"},
        {"id": 2, "email": "a@x.com", "age": -1, "joined": "0000-00-00"},
        {"id": 3, "email": "", "age": 41, "joined": "2021-06-01"},
        {"id": 4, "email": "d@x.com", "age": -1, "joined": "1970-01-01"},
    ],
    "orders": [
        {"id": 10, "user_id": 1},
        {"id": 11, "user_id": 999},   # orphan — no such user
        {"id": 12, "user_id": 2},
    ],
}


def _kinds(report):
    return {i["kind"] for i in report["issues"]}


def test_detects_duplicate_in_unique_column():
    report = build_data_quality_report(SCHEMA, SAMPLES)
    assert "duplicate_in_unique" in _kinds(report)
    dup = next(i for i in report["issues"] if i["kind"] == "duplicate_in_unique")
    assert dup["column"] == "email"
    assert dup["severity"] == "high"


def test_detects_empty_string_in_not_null():
    report = build_data_quality_report(SCHEMA, SAMPLES)
    issue = next(i for i in report["issues"]
                 if i["kind"] == "empty_string_in_not_null")
    assert issue["column"] == "email"


def test_detects_sentinel_dates():
    report = build_data_quality_report(SCHEMA, SAMPLES)
    issue = next(i for i in report["issues"] if i["kind"] == "sentinel_date")
    assert issue["column"] == "joined"


def test_detects_numeric_sentinels():
    report = build_data_quality_report(SCHEMA, SAMPLES)
    issue = next(i for i in report["issues"] if i["kind"] == "numeric_sentinel")
    assert issue["column"] == "age"


def test_detects_orphaned_rows():
    report = build_data_quality_report(SCHEMA, SAMPLES)
    issue = next(i for i in report["issues"] if i["kind"] == "orphaned_rows")
    assert issue["table"] == "orders"
    assert issue["severity"] == "high"


def test_quality_score_drops_with_issues():
    report = build_data_quality_report(SCHEMA, SAMPLES)
    assert 0 <= report["quality_score"] < 100
    clean = build_data_quality_report(
        {"users": {**SCHEMA["users"], "indexes": [], "row_count": 1}},
        {"users": [{"id": 1, "email": "a@x.com", "age": 30,
                    "joined": "2020-01-01"}]})
    assert clean["quality_score"] == 100
    assert clean["issues"] == []


def test_orphan_check_skipped_when_parent_sample_is_partial():
    """A subset sample of the parent can't prove a child row is orphaned."""
    schema = {**SCHEMA, "users": {**SCHEMA["users"], "row_count": 10_000}}
    report = build_data_quality_report(schema, SAMPLES)
    assert "orphaned_rows" not in _kinds(report)


JOB = {
    "id": "job-1", "name": "demo",
    "target_db_type": "postgres",
    "schema_snapshot": {"tables": SCHEMA},
    "migration_plan": {"tables": [
        {"source_table": "users", "target_table_name": "users",
         "column_mappings": []},
        {"source_table": "orders", "target_table_name": "orders",
         "column_mappings": []},
    ]},
}


def test_rollback_drops_children_before_parents():
    sql = generate_rollback_script(JOB)
    assert sql.index('DROP TABLE IF EXISTS "orders"') < \
        sql.index('DROP TABLE IF EXISTS "users"')
    assert "manual rollback GUIDE" in sql
    assert "CASCADE" in sql


def test_rollback_uses_mysql_quoting():
    sql = generate_rollback_script({**JOB, "target_db_type": "mysql"})
    assert "DROP TABLE IF EXISTS `orders`;" in sql
    assert "CASCADE" not in sql


def test_rollback_for_mongo_emits_drop_calls():
    sql = generate_rollback_script({**JOB, "target_db_type": "mongodb"})
    assert 'db.getCollection("orders").drop();' in sql


SPEC = {
    "source_table": "users", "target_table_name": "users",
    "column_mappings": [
        {"source_column": "is_active", "target_column": "is_active",
         "source_type": "TINYINT(1)", "target_type": "BOOLEAN"},
        {"source_column": "price", "target_column": "price",
         "source_type": "FLOAT", "target_type": "DECIMAL(10,2)"},
        {"source_column": "name", "target_column": "name",
         "source_type": "VARCHAR", "target_type": "TEXT"},
    ],
}


def test_simulation_flags_changed_cells():
    rows = [{"is_active": 1, "price": 9.999, "name": "ada"}]
    result = simulate_table(rows, SPEC)
    row = result["rows"][0]
    assert row["transformed"]["is_active"] is True
    assert row["transformed"]["price"] == 10.0
    assert set(row["changed_columns"]) == {"is_active", "price"}
    assert result["rows_with_changes"] == 1


def test_simulation_reports_unchanged_rows():
    rows = [{"is_active": True, "price": 10.0, "name": "ada"}]
    result = simulate_table(rows, SPEC)
    assert result["rows"][0]["changed_columns"] == []
    assert result["rows_with_changes"] == 0


def test_simulation_caps_preview_rows_but_counts_all():
    rows = [{"is_active": 1, "price": 1.0, "name": f"n{i}"} for i in range(300)]
    result = simulate_table(rows, SPEC)
    assert result["rows_simulated"] == 300
    assert len(result["rows"]) == 50
    assert result["rows_with_changes"] == 300

"""Agent pipeline tests — run fully offline on SQLite with the fallback planner."""
from __future__ import annotations

import pytest

from app.agents import (
    DataProfiler,
    MappingStrategist,
    MigrationExecutor,
    SchemaAnalyst,
    ValidationAuditor,
)
from app.utils.type_mapper import map_type, normalise_type

JOB = "test-job-1"


class TestTypeMapper:
    def test_mysql_tinyint1_is_boolean(self):
        assert normalise_type("mysql", "tinyint(1)") == "boolean"
        assert map_type("mysql", "postgres", "tinyint(1)") == "BOOLEAN"

    def test_mysql_datetime_to_pg(self):
        assert map_type("mysql", "postgres", "datetime") == "TIMESTAMPTZ"

    def test_any_to_sqlite_downgrades(self):
        assert map_type("postgres", "sqlite", "boolean") == "INTEGER"
        assert map_type("postgres", "sqlite", "jsonb") == "TEXT"
        assert map_type("postgres", "sqlite", "uuid") == "TEXT"

    def test_unknown_falls_back_to_text(self):
        assert map_type("postgres", "mysql", "hstore_weird") == "TEXT"


class TestSchemaAnalyst:
    async def test_run(self, source_connector):
        snapshot = await SchemaAnalyst(source_connector, JOB).run()
        assert snapshot["summary"]["table_count"] == 2
        assert snapshot["summary"]["total_rows"] == 170
        assert "orders" in snapshot["summary"]["tables_with_fks"]


class TestDataProfiler:
    async def test_run(self, source_connector):
        schema = await SchemaAnalyst(source_connector, JOB).run()
        profile = await DataProfiler(source_connector, schema, JOB).run()
        users = profile["tables"]["users"]["columns"]
        # email + phone flagged as PII (test case 6 from CLAUDE.md)
        assert users["email"]["pii_suspected"] is True
        assert users["phone"]["pii_suspected"] is True
        # is_verified only holds 0/1 → implicit boolean
        assert users["is_verified"]["implicit_boolean"] is True
        # status has 3 distinct string values → implicit enum
        assert users["status"]["implicit_enum"] is True
        assert set(users["status"]["enum_values"]) == {"active", "inactive", "banned"}
        # phone has NULLs every 5th row
        assert users["phone"]["null_pct"] == 20.0
        assert "users.email" in profile["summary"]["pii_fields"]


class TestMappingStrategist:
    async def test_fallback_plan(self, source_connector):
        schema = await SchemaAnalyst(source_connector, JOB).run()
        profile = await DataProfiler(source_connector, schema, JOB).run()
        plan = await MappingStrategist(
            schema, profile, "sqlite", "postgres", {}, JOB).run()
        tables = {t["source_table"]: t for t in plan["tables"]}
        assert set(tables) == {"users", "orders"}
        # FK-safe order: users before orders
        order = plan["execution_order"]
        assert order.index("users") < order.index("orders")
        id_map = next(m for m in tables["users"]["column_mappings"]
                      if m["source_column"] == "id")
        assert id_map["target_type"] == "BIGINT"

    async def test_skip_tables_option(self, source_connector):
        schema = await SchemaAnalyst(source_connector, JOB).run()
        plan = await MappingStrategist(
            schema, {"tables": {}}, "sqlite", "sqlite",
            {"skip_tables": ["orders"]}, JOB).run()
        assert [t["source_table"] for t in plan["tables"]] == ["users"]


class TestExecutorAndAuditor:
    async def test_full_migration_sqlite_to_sqlite(self, source_connector, target_connector):
        schema = await SchemaAnalyst(source_connector, JOB).run()
        profile = await DataProfiler(source_connector, schema, JOB).run()
        plan = await MappingStrategist(
            schema, profile, "sqlite", "sqlite", {}, JOB).run()

        progress: list[tuple[int, int, int]] = []

        async def progress_sink(migrated, total, pct):
            progress.append((migrated, total, pct))

        report = await MigrationExecutor(
            source_connector, target_connector, plan, JOB,
            chunk_size=40, progress_sink=progress_sink).run()
        assert report["rows_migrated"] == 170
        assert report["rows_total"] == 170
        assert report["errors"] == []
        assert progress[-1][2] == 100
        # progress written every chunk: users 50/40 → 2 chunks, orders 120/40 → 3
        assert len(progress) == 5

        assert await target_connector.count_rows("users") == 50
        assert await target_connector.count_rows("orders") == 120

        validation = await ValidationAuditor(
            source_connector, target_connector, plan, JOB).run()
        assert validation["passed"] is True
        assert validation["confidence_score"] >= 90
        assert validation["flagged_tables"] == []
        assert validation["tables"]["users"]["row_count_ok"] is True

    async def test_auditor_flags_mismatch(self, source_connector, target_connector):
        schema = await SchemaAnalyst(source_connector, JOB).run()
        plan = await MappingStrategist(
            schema, {"tables": {}}, "sqlite", "sqlite", {}, JOB).run()
        await MigrationExecutor(source_connector, target_connector, plan, JOB).run()
        # sabotage: delete rows from target
        await target_connector.execute("DELETE FROM orders WHERE id <= 10")
        validation = await ValidationAuditor(
            source_connector, target_connector, plan, JOB).run()
        assert "orders" in validation["flagged_tables"]
        assert validation["passed"] is False

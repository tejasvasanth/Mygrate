"""Connector tests — SQLite runs everywhere; postgres/mysql/mongo need docker."""
from __future__ import annotations

import pytest

from app.connectors import get_connector
from app.connectors.connector_factory import SUPPORTED_DB_TYPES


class TestFactory:
    def test_known_types(self):
        for t in ("postgres", "mysql", "mongodb", "sqlite",
                  "aurora-postgres", "mariadb", "cosmosdb-mongo",
                  "sqlserver", "azure-sql", "bigquery", "dynamodb", "neo4j"):
            assert t in SUPPORTED_DB_TYPES

    def test_aliases_resolve(self):
        pairs = [("aurora-postgres", "PostgresConnector", "postgresql://u:p@h/d"),
                 ("planetscale", "MySQLConnector", "mysql://u:p@h/d"),
                 ("documentdb", "MongoDBConnector", "mongodb://u:p@h/d"),
                 ("azure-sql", "SQLServerConnector", "mssql://u:p@h:1433/d"),
                 ("bigquery", "BigQueryConnector", "bigquery://proj/ds"),
                 ("dynamodb", "DynamoDBConnector", "dynamodb://k:s@us-east-1"),
                 ("neo4j", "Neo4jConnector", "neo4j://u:p@h:7687")]
        for db_type, cls_name, cs in pairs:
            assert type(get_connector(db_type, cs)).__name__ == cls_name

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            get_connector("oracle", "oracle://x")


class TestSQLiteConnector:
    async def test_connection(self, source_connector):
        assert await source_connector.test_connection()

    async def test_schema(self, source_connector):
        schema = await source_connector.get_schema()
        assert schema["db_type"] == "sqlite"
        assert set(schema["tables"]) == {"users", "orders"}
        users = schema["tables"]["users"]
        assert users["primary_key"] == ["id"]
        assert users["row_count"] == 50
        cols = {c["name"]: c for c in users["columns"]}
        assert cols["email"]["nullable"] is False
        assert cols["phone"]["nullable"] is True
        orders = schema["tables"]["orders"]
        assert orders["foreign_keys"] == [
            {"column": "user_id", "ref_table": "users", "ref_column": "id"}]

    async def test_count_and_sample(self, source_connector):
        assert await source_connector.count_rows("orders") == 120
        rows = await source_connector.sample_rows("users", 10)
        assert len(rows) == 10
        assert "email" in rows[0]

    async def test_stream_rows_chunked(self, source_connector):
        chunks = []
        async for chunk in source_connector.stream_rows("orders", chunk_size=50):
            chunks.append(chunk)
        assert [len(c) for c in chunks] == [50, 50, 20]
        ids = [r["id"] for c in chunks for r in c]
        assert ids == sorted(ids)
        assert len(set(ids)) == 120

    async def test_create_and_insert(self, target_connector):
        await target_connector.create_table(
            "t1", [{"name": "id", "type": "INTEGER", "nullable": False},
                   {"name": "v", "type": "TEXT", "nullable": True}],
            primary_key=["id"])
        n = await target_connector.insert_rows(
            "t1", [{"id": 1, "v": "a"}, {"id": 2, "v": None}])
        assert n == 2
        assert await target_connector.count_rows("t1") == 2

    async def test_conflict_skip(self, target_connector):
        await target_connector.create_table(
            "t2", [{"name": "id", "type": "INTEGER", "nullable": False}],
            primary_key=["id"])
        await target_connector.insert_rows("t2", [{"id": 1}])
        n = await target_connector.insert_rows(
            "t2", [{"id": 1}, {"id": 2}], conflict_strategy="skip")
        assert await target_connector.count_rows("t2") == 2
        assert n == 2  # driver reports statements executed


# ── Optional: dockerised databases (skipped when not reachable) ──
async def _reachable(connector) -> bool:
    try:
        await connector.test_connection()
        return True
    except Exception:
        return False
    finally:
        await connector.close()


@pytest.mark.docker
async def test_postgres_schema():
    c = get_connector("postgres", "postgresql://testuser:testpass@localhost:5433/testdb")
    if not await _reachable(c):
        pytest.skip("test-postgres not running (docker-compose up -d)")
    async with get_connector(
            "postgres", "postgresql://testuser:testpass@localhost:5433/testdb") as c:
        schema = await c.get_schema()
        assert {"users", "orders", "products", "audit_logs"} <= set(schema["tables"])
        assert schema["tables"]["users"]["row_count"] == 500


@pytest.mark.docker
async def test_mysql_schema():
    c = get_connector("mysql", "mysql://testuser:testpass@localhost:3307/testdb")
    if not await _reachable(c):
        pytest.skip("test-mysql not running (docker-compose up -d)")
    async with get_connector(
            "mysql", "mysql://testuser:testpass@localhost:3307/testdb") as c:
        schema = await c.get_schema()
        assert {"users", "orders", "products", "audit_logs"} <= set(schema["tables"])
        cols = {x["name"]: x for x in schema["tables"]["users"]["columns"]}
        assert cols["is_verified"]["type"].startswith("tinyint(1)")


@pytest.mark.docker
async def test_mongodb_schema():
    c = get_connector("mongodb", "mongodb://localhost:27018/testdb")
    if not await _reachable(c):
        pytest.skip("test-mongo not running (docker-compose up -d)")
    async with get_connector("mongodb", "mongodb://localhost:27018/testdb") as c:
        schema = await c.get_schema()
        assert "users" in schema["tables"]
        cols = {x["name"]: x for x in schema["tables"]["users"]["columns"]}
        assert "orders" in cols and cols["orders"]["type"] == "array"
        # loyalty_tier only on ~20% of docs → flagged optional
        assert cols["loyalty_tier"]["optional"] is True

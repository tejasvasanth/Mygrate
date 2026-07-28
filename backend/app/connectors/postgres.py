"""PostgreSQL connector (asyncpg via SQLAlchemy async)."""
from __future__ import annotations

from typing import Any

from ._sql_common import SQLConnector


class PostgresConnector(SQLConnector):
    db_type = "postgres"
    quote_char = '"'

    def __init__(self, connection_string: str):
        cs = connection_string
        if cs.startswith("postgresql+asyncpg"):
            pass
        elif cs.startswith("postgresql:"):
            cs = cs.replace("postgresql:", "postgresql+asyncpg:", 1)
        elif cs.startswith("postgres:"):
            cs = cs.replace("postgres:", "postgresql+asyncpg:", 1)
        super().__init__(cs)

    async def _introspect_schema(self) -> dict[str, Any]:
        tables: dict[str, Any] = {}
        cols = await self.fetch_all("""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """)
        pks = await self.fetch_all("""
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public'
        """)
        fks = await self.fetch_all("""
            SELECT tc.table_name, kcu.column_name,
                   ccu.table_name AS ref_table, ccu.column_name AS ref_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
             AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
        """)
        idx = await self.fetch_all(
            "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'")

        pk_map: dict[str, list[str]] = {}
        for r in pks:
            pk_map.setdefault(r["table_name"], []).append(r["column_name"])
        fk_map: dict[str, list[dict[str, str]]] = {}
        for r in fks:
            fk_map.setdefault(r["table_name"], []).append({
                "column": r["column_name"], "ref_table": r["ref_table"],
                "ref_column": r["ref_column"],
            })
        idx_map: dict[str, list[dict[str, Any]]] = {}
        for r in idx:
            idx_map.setdefault(r["tablename"], []).append({
                "name": r["indexname"], "columns": [],
                "unique": "UNIQUE" in (r["indexdef"] or "").upper(),
            })

        for c in cols:
            t = c["table_name"]
            if t not in tables:
                tables[t] = {
                    "columns": [], "primary_key": pk_map.get(t, []),
                    "foreign_keys": fk_map.get(t, []), "indexes": idx_map.get(t, []),
                }
            tables[t]["columns"].append({
                "name": c["column_name"],
                "type": c["data_type"].lower(),
                "nullable": c["is_nullable"] == "YES",
                "default": c["column_default"],
                "primary_key": c["column_name"] in pk_map.get(t, []),
            })
        for t in tables:
            tables[t]["row_count"] = await self.count_rows(t)
        return {"db_type": self.db_type, "tables": tables}

    def _insert_suffix(self, table: str, columns: list[str], conflict_strategy: str) -> str:
        if conflict_strategy == "skip":
            return " ON CONFLICT DO NOTHING"
        return ""

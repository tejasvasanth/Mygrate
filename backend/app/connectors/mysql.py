"""MySQL connector (aiomysql via SQLAlchemy async)."""
from __future__ import annotations

from typing import Any

from ._sql_common import SQLConnector


class MySQLConnector(SQLConnector):
    db_type = "mysql"
    quote_char = "`"

    def __init__(self, connection_string: str):
        cs = connection_string
        if cs.startswith("mysql+aiomysql"):
            pass
        elif cs.startswith("mysql:"):
            cs = cs.replace("mysql:", "mysql+aiomysql:", 1)
        super().__init__(cs)

    async def _introspect_schema(self) -> dict[str, Any]:
        tables: dict[str, Any] = {}
        cols = await self.fetch_all("""
            SELECT TABLE_NAME AS table_name, COLUMN_NAME AS column_name,
                   COLUMN_TYPE AS column_type, DATA_TYPE AS data_type,
                   IS_NULLABLE AS is_nullable, COLUMN_DEFAULT AS column_default,
                   COLUMN_KEY AS column_key
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            ORDER BY TABLE_NAME, ORDINAL_POSITION
        """)
        fks = await self.fetch_all("""
            SELECT TABLE_NAME AS table_name, COLUMN_NAME AS column_name,
                   REFERENCED_TABLE_NAME AS ref_table, REFERENCED_COLUMN_NAME AS ref_column
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
        """)
        idx = await self.fetch_all("""
            SELECT TABLE_NAME AS table_name, INDEX_NAME AS index_name,
                   COLUMN_NAME AS column_name, NON_UNIQUE AS non_unique
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
        """)

        fk_map: dict[str, list[dict[str, str]]] = {}
        for r in fks:
            fk_map.setdefault(r["table_name"], []).append({
                "column": r["column_name"], "ref_table": r["ref_table"],
                "ref_column": r["ref_column"],
            })
        idx_map: dict[str, dict[str, dict[str, Any]]] = {}
        for r in idx:
            t = idx_map.setdefault(r["table_name"], {})
            entry = t.setdefault(r["index_name"], {
                "name": r["index_name"], "columns": [], "unique": not r["non_unique"],
            })
            entry["columns"].append(r["column_name"])

        for c in cols:
            t = c["table_name"]
            if t not in tables:
                tables[t] = {
                    "columns": [], "primary_key": [],
                    "foreign_keys": fk_map.get(t, []),
                    "indexes": list(idx_map.get(t, {}).values()),
                }
            is_pk = c["column_key"] == "PRI"
            # COLUMN_TYPE keeps tinyint(1) so booleans survive normalisation.
            tables[t]["columns"].append({
                "name": c["column_name"],
                "type": (c["column_type"] or c["data_type"]).lower(),
                "nullable": c["is_nullable"] == "YES",
                "default": c["column_default"],
                "primary_key": is_pk,
            })
            if is_pk:
                tables[t]["primary_key"].append(c["column_name"])
        for t in tables:
            tables[t]["row_count"] = await self.count_rows(t)
        return {"db_type": self.db_type, "tables": tables}

    def _insert_prefix(self, conflict_strategy: str) -> str:
        if conflict_strategy == "skip":
            return "INSERT IGNORE INTO"
        if conflict_strategy == "overwrite":
            return "REPLACE INTO"
        return "INSERT INTO"

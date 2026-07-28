"""SQLite connector (aiosqlite via SQLAlchemy async)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from ._sql_common import SQLConnector


class SQLiteConnector(SQLConnector):
    db_type = "sqlite"
    quote_char = '"'

    def __init__(self, connection_string: str):
        # Accept a bare file path, sqlite:///path, or sqlite+aiosqlite:///path.
        cs = connection_string
        if cs.startswith("sqlite+aiosqlite"):
            pass
        elif cs.startswith("sqlite:"):
            cs = cs.replace("sqlite:", "sqlite+aiosqlite:", 1)
        else:
            cs = f"sqlite+aiosqlite:///{cs}"
        super().__init__(cs)

    async def _introspect_schema(self) -> dict[str, Any]:
        tables: dict[str, Any] = {}
        names = await self.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")
        for row in names:
            table = row["name"]
            cols = await self.fetch_all(f"PRAGMA table_info({self.q(table)})")
            fks = await self.fetch_all(f"PRAGMA foreign_key_list({self.q(table)})")
            idx = await self.fetch_all(f"PRAGMA index_list({self.q(table)})")
            columns = [{
                "name": c["name"],
                "type": (c["type"] or "TEXT").lower(),
                "nullable": not c["notnull"],
                "default": c["dflt_value"],
                "primary_key": bool(c["pk"]),
            } for c in cols]
            indexes = []
            for i in idx:
                icols = await self.fetch_all(f"PRAGMA index_info({self.q(i['name'])})")
                indexes.append({
                    "name": i["name"],
                    "columns": [ic["name"] for ic in icols],
                    "unique": bool(i["unique"]),
                })
            tables[table] = {
                "columns": columns,
                "primary_key": [c["name"] for c in columns if c["primary_key"]],
                "foreign_keys": [{
                    "column": f["from"], "ref_table": f["table"], "ref_column": f["to"],
                } for f in fks],
                "indexes": indexes,
                "row_count": await self.count_rows(table),
            }
        return {"db_type": self.db_type, "tables": tables}

    def _adapt_value(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, bool):
            return int(value)
        return value

    async def add_foreign_key(self, table: str, column: str,
                              ref_table: str, ref_column: str) -> None:
        # SQLite cannot ALTER TABLE ... ADD FOREIGN KEY after creation.
        raise NotImplementedError("SQLite cannot add FK constraints post-create")

    def _insert_prefix(self, conflict_strategy: str) -> str:
        if conflict_strategy == "skip":
            return "INSERT OR IGNORE INTO"
        if conflict_strategy == "overwrite":
            return "INSERT OR REPLACE INTO"
        return "INSERT INTO"

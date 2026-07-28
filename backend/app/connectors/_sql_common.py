"""Shared SQLAlchemy-based implementation for relational connectors."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .base import BaseConnector


class SQLConnector(BaseConnector):
    """Common machinery for PostgreSQL / MySQL / SQLite via async SQLAlchemy."""

    quote_char = '"'

    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        self.engine: AsyncEngine | None = None
        self._schema_cache: dict[str, Any] | None = None

    async def get_schema(self) -> dict[str, Any]:
        if self._schema_cache is None:
            self._schema_cache = await self._introspect_schema()
        return self._schema_cache

    async def _introspect_schema(self) -> dict[str, Any]:
        raise NotImplementedError

    async def connect(self) -> None:
        if self.engine is None:
            self.engine = create_async_engine(self.connection_string, pool_pre_ping=True)

    async def close(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
            self.engine = None

    async def test_connection(self) -> bool:
        await self.connect()
        assert self.engine is not None
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True

    def q(self, identifier: str) -> str:
        c = self.quote_char
        return f"{c}{identifier.replace(c, c * 2)}{c}"

    async def execute(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        assert self.engine is not None, "connect() first"
        async with self.engine.begin() as conn:
            return await conn.execute(text(sql), params or {})

    async def fetch_all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        assert self.engine is not None, "connect() first"
        async with self.engine.connect() as conn:
            result = await conn.execute(text(sql), params or {})
            return [dict(row._mapping) for row in result]

    async def count_rows(self, table: str) -> int:
        rows = await self.fetch_all(f"SELECT COUNT(*) AS n FROM {self.q(table)}")
        return int(rows[0]["n"])

    async def sample_rows(self, table: str, limit: int = 1000) -> list[dict[str, Any]]:
        return await self.fetch_all(f"SELECT * FROM {self.q(table)} LIMIT {int(limit)}")

    async def stream_rows(self, table: str, chunk_size: int = 1000,
                          start_after: Any = None,
                          skip_rows: int = 0) -> AsyncIterator[list[dict[str, Any]]]:
        """Keyset pagination on the primary key when one exists, OFFSET otherwise.

        start_after resumes a keyset scan past an already-committed primary key;
        skip_rows does the same for the OFFSET path (see T2-3 checkpointing).
        """
        pk = await self._single_pk(table)
        if pk:
            last: Any = start_after
            while True:
                if last is None:
                    sql = f"SELECT * FROM {self.q(table)} ORDER BY {self.q(pk)} LIMIT {int(chunk_size)}"
                    rows = await self.fetch_all(sql)
                else:
                    sql = (f"SELECT * FROM {self.q(table)} WHERE {self.q(pk)} > :last "
                           f"ORDER BY {self.q(pk)} LIMIT {int(chunk_size)}")
                    rows = await self.fetch_all(sql, {"last": last})
                if not rows:
                    break
                yield rows
                last = rows[-1][pk]
                if len(rows) < chunk_size:
                    break
        else:
            # No single PK: OFFSET pagination needs a deterministic order or
            # rows can repeat/skip between pages. Order by every column.
            schema = await self.get_schema()
            cols = [c["name"] for c in schema["tables"].get(table, {}).get("columns", [])]
            order_sql = (" ORDER BY " + ", ".join(self.q(c) for c in cols)) if cols else ""
            offset = max(0, int(skip_rows))
            while True:
                rows = await self.fetch_all(
                    f"SELECT * FROM {self.q(table)}{order_sql} "
                    f"LIMIT {int(chunk_size)} OFFSET {offset}")
                if not rows:
                    break
                yield rows
                offset += len(rows)
                if len(rows) < chunk_size:
                    break

    async def _single_pk(self, table: str) -> str | None:
        schema = await self.get_schema()
        info = schema["tables"].get(table, {})
        pk = info.get("primary_key") or []
        return pk[0] if len(pk) == 1 else None

    async def create_table(self, table: str, columns: list[dict[str, Any]],
                           primary_key: list[str] | None = None) -> None:
        cols = []
        for col in columns:
            null_sql = "" if col.get("nullable", True) else " NOT NULL"
            cols.append(f"{self.q(col['name'])} {col['type']}{null_sql}")
        if primary_key:
            cols.append("PRIMARY KEY (" + ", ".join(self.q(c) for c in primary_key) + ")")
        sql = f"CREATE TABLE IF NOT EXISTS {self.q(table)} (\n  " + ",\n  ".join(cols) + "\n)"
        await self.execute(sql)

    async def drop_table(self, table: str) -> None:
        await self.execute(f"DROP TABLE IF EXISTS {self.q(table)}")

    async def fetch_rows_by_key(self, table: str, key_column: str,
                                values: list[Any]) -> list[dict[str, Any]]:
        if not values:
            return []
        from sqlalchemy import bindparam
        assert self.engine is not None, "connect() first"
        sql = text(f"SELECT * FROM {self.q(table)} "
                   f"WHERE {self.q(key_column)} IN :vals").bindparams(
            bindparam("vals", expanding=True))
        async with self.engine.connect() as conn:
            result = await conn.execute(sql, {"vals": list(values)})
            return [dict(row._mapping) for row in result]

    async def add_foreign_key(self, table: str, column: str,
                              ref_table: str, ref_column: str) -> None:
        await self.execute(
            f"ALTER TABLE {self.q(table)} ADD FOREIGN KEY ({self.q(column)}) "
            f"REFERENCES {self.q(ref_table)} ({self.q(ref_column)})")

    def _insert_prefix(self, conflict_strategy: str) -> str:
        return "INSERT INTO"

    def _insert_suffix(self, table: str, columns: list[str], conflict_strategy: str) -> str:
        return ""

    async def insert_rows(self, table: str, rows: list[dict[str, Any]],
                          conflict_strategy: str = "fail") -> int:
        if not rows:
            return 0
        columns = list(rows[0].keys())
        col_sql = ", ".join(self.q(c) for c in columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        sql = (f"{self._insert_prefix(conflict_strategy)} {self.q(table)} ({col_sql}) "
               f"VALUES ({placeholders})"
               f"{self._insert_suffix(table, columns, conflict_strategy)}")
        assert self.engine is not None
        async with self.engine.begin() as conn:
            await conn.execute(
                text(sql),
                [{c: self._adapt_value(r.get(c)) for c in columns} for r in rows])
        return len(rows)

    def _adapt_value(self, value: Any) -> Any:
        """Coerce driver-unsupported Python types before binding. Overridden
        per target — SQLite in particular cannot bind Decimal/datetime/UUID."""
        return value

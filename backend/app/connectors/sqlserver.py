"""SQL Server / Azure SQL connector (pyodbc, run in threads).

Accepts either a full ODBC connection string
("Driver={ODBC Driver 18 for SQL Server};Server=...;...") or a URL of the form
mssql://user:password@host:port/database — converted to ODBC automatically.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import unquote, urlparse

from .base import BaseConnector

DEFAULT_DRIVER = "ODBC Driver 18 for SQL Server"


def _to_odbc(connection_string: str) -> str:
    cs = connection_string.strip()
    if "://" not in cs:
        return cs  # already an ODBC string
    u = urlparse(cs)
    parts = [
        f"Driver={{{DEFAULT_DRIVER}}}",
        f"Server={u.hostname or 'localhost'},{u.port or 1433}",
        f"Database={(u.path or '/').lstrip('/')}",
        "TrustServerCertificate=yes",
        "Encrypt=yes",
    ]
    if u.username:
        parts.append(f"UID={unquote(u.username)}")
        parts.append(f"PWD={unquote(u.password or '')}")
    else:
        parts.append("Trusted_Connection=yes")
    return ";".join(parts)


class SQLServerConnector(BaseConnector):
    db_type = "sqlserver"

    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        self.conn: Any = None

    async def connect(self) -> None:
        if self.conn is None:
            import pyodbc

            def _mk():
                c = pyodbc.connect(_to_odbc(self.connection_string), timeout=10)
                c.autocommit = True
                return c
            self.conn = await asyncio.to_thread(_mk)

    async def close(self) -> None:
        if self.conn is not None:
            await asyncio.to_thread(self.conn.close)
            self.conn = None

    def _query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = [dict(zip(cols, r)) for r in cur.fetchall()] if cols else []
        cur.close()
        return rows

    async def _q(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        await self.connect()
        return await asyncio.to_thread(self._query, sql, params)

    async def test_connection(self) -> bool:
        await self._q("SELECT 1 AS ok")
        return True

    async def get_schema(self) -> dict[str, Any]:
        tables: dict[str, Any] = {}
        for t in await self._q(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE='BASE TABLE' AND TABLE_SCHEMA='dbo'"):
            name = t["TABLE_NAME"]
            cols = await self._q(
                "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT "
                "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? "
                "ORDER BY ORDINAL_POSITION", (name,))
            pks = [r["COLUMN_NAME"] for r in await self._q(
                "SELECT ku.COLUMN_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
                "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku "
                "ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME "
                "WHERE tc.CONSTRAINT_TYPE='PRIMARY KEY' AND ku.TABLE_NAME=?", (name,))]
            fks = await self._q(
                "SELECT cu.COLUMN_NAME AS col, pt.TABLE_NAME AS ref_table, "
                "ptu.COLUMN_NAME AS ref_column "
                "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
                "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE cu "
                "ON rc.CONSTRAINT_NAME = cu.CONSTRAINT_NAME "
                "JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS pt "
                "ON rc.UNIQUE_CONSTRAINT_NAME = pt.CONSTRAINT_NAME "
                "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ptu "
                "ON pt.CONSTRAINT_NAME = ptu.CONSTRAINT_NAME "
                "WHERE cu.TABLE_NAME=?", (name,))
            count = (await self._q(f"SELECT COUNT(*) AS c FROM [{name}]"))[0]["c"]
            tables[name] = {
                "columns": [{
                    "name": c["COLUMN_NAME"], "type": c["DATA_TYPE"],
                    "nullable": c["IS_NULLABLE"] == "YES",
                    "default": c["COLUMN_DEFAULT"],
                    "primary_key": c["COLUMN_NAME"] in pks,
                } for c in cols],
                "primary_key": pks,
                "foreign_keys": [{"column": f["col"], "ref_table": f["ref_table"],
                                  "ref_column": f["ref_column"]} for f in fks],
                "indexes": [],
                "row_count": count,
            }
        return {"db_type": self.db_type, "tables": tables}

    async def count_rows(self, table: str) -> int:
        return (await self._q(f"SELECT COUNT(*) AS c FROM [{table}]"))[0]["c"]

    async def sample_rows(self, table: str, limit: int = 1000) -> list[dict[str, Any]]:
        return await self._q(f"SELECT TOP {int(limit)} * FROM [{table}]")

    async def stream_rows(self, table: str, chunk_size: int = 1000,
                          start_after: Any = None,
                          skip_rows: int = 0) -> AsyncIterator[list[dict[str, Any]]]:
        schema = await self.get_schema()
        pks = schema["tables"].get(table, {}).get("primary_key", [])
        order = ", ".join(f"[{c}]" for c in pks) if pks else "(SELECT NULL)"
        offset = max(0, int(skip_rows))
        while True:
            rows = await self._q(
                f"SELECT * FROM [{table}] ORDER BY {order} "
                f"OFFSET {offset} ROWS FETCH NEXT {int(chunk_size)} ROWS ONLY")
            if not rows:
                break
            yield rows
            offset += len(rows)
            if len(rows) < chunk_size:
                break

    async def create_table(self, table: str, columns: list[dict[str, Any]],
                           primary_key: list[str] | None = None) -> None:
        defs = [f"[{c['name']}] {c['type']}"
                f"{'' if c.get('nullable', True) else ' NOT NULL'}" for c in columns]
        if primary_key:
            defs.append("PRIMARY KEY (" + ", ".join(f"[{c}]" for c in primary_key) + ")")
        sql = (f"IF OBJECT_ID(N'[{table}]', N'U') IS NULL "
               f"CREATE TABLE [{table}] ({', '.join(defs)})")
        await self._q(sql)

    async def insert_rows(self, table: str, rows: list[dict[str, Any]],
                          conflict_strategy: str = "fail") -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        placeholders = ", ".join("?" for _ in cols)
        col_sql = ", ".join(f"[{c}]" for c in cols)
        sql = f"INSERT INTO [{table}] ({col_sql}) VALUES ({placeholders})"

        def _insert() -> int:
            cur = self.conn.cursor()
            written = 0
            if conflict_strategy == "fail":
                cur.fast_executemany = True
                cur.executemany(sql, [[r.get(c) for c in cols] for r in rows])
                written = len(rows)
            else:  # skip / overwrite: per-row so one conflict doesn't kill the batch
                for r in rows:
                    try:
                        cur.execute(sql, [r.get(c) for c in cols])
                        written += 1
                    except Exception:
                        if conflict_strategy == "skip":
                            continue
                        raise
            cur.close()
            return written
        return await asyncio.to_thread(_insert)

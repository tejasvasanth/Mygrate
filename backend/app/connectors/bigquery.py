"""Google BigQuery connector.

Connection string format:
  bigquery://<project>/<dataset>
  bigquery://<project>/<dataset>?credentials_path=C:/path/service-account.json

Without credentials_path, Application Default Credentials are used
(GOOGLE_APPLICATION_CREDENTIALS env var or gcloud auth).
"""
from __future__ import annotations

import asyncio
import datetime
import decimal
import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs, urlparse

from .base import BaseConnector


def _parse(cs: str) -> tuple[str, str, str | None]:
    u = urlparse(cs)
    project = u.hostname or ""
    dataset = (u.path or "/").lstrip("/")
    creds = (parse_qs(u.query).get("credentials_path") or [None])[0]
    if not project or not dataset:
        raise ValueError("BigQuery connection string must be "
                         "bigquery://<project>/<dataset>")
    return project, dataset, creds


class BigQueryConnector(BaseConnector):
    db_type = "bigquery"

    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        self.project, self.dataset, self.credentials_path = _parse(connection_string)
        self.client: Any = None

    async def connect(self) -> None:
        if self.client is None:
            from google.cloud import bigquery

            def _mk():
                if self.credentials_path:
                    from google.oauth2 import service_account
                    creds = service_account.Credentials.from_service_account_file(
                        self.credentials_path)
                    return bigquery.Client(project=self.project, credentials=creds)
                return bigquery.Client(project=self.project)
            self.client = await asyncio.to_thread(_mk)

    async def close(self) -> None:
        if self.client is not None:
            await asyncio.to_thread(self.client.close)
            self.client = None

    def _ref(self, table: str) -> str:
        return f"{self.project}.{self.dataset}.{table}"

    async def _query(self, sql: str) -> list[dict[str, Any]]:
        await self.connect()

        def _run():
            return [dict(r) for r in self.client.query(sql).result()]
        return await asyncio.to_thread(_run)

    async def test_connection(self) -> bool:
        await self.connect()
        await asyncio.to_thread(self.client.get_dataset, f"{self.project}.{self.dataset}")
        return True

    async def get_schema(self) -> dict[str, Any]:
        await self.connect()

        def _scan() -> dict[str, Any]:
            tables: dict[str, Any] = {}
            for item in self.client.list_tables(f"{self.project}.{self.dataset}"):
                t = self.client.get_table(item.reference)
                tables[t.table_id] = {
                    "columns": [{
                        "name": f.name, "type": f.field_type.lower(),
                        "nullable": f.mode != "REQUIRED", "default": None,
                        "primary_key": False,
                    } for f in t.schema],
                    "primary_key": [],   # BigQuery has no enforced PKs
                    "foreign_keys": [],
                    "indexes": [],
                    "row_count": int(t.num_rows or 0),
                }
            return {"db_type": self.db_type, "tables": tables}
        return await asyncio.to_thread(_scan)

    async def count_rows(self, table: str) -> int:
        rows = await self._query(f"SELECT COUNT(*) AS c FROM `{self._ref(table)}`")
        return int(rows[0]["c"])

    async def sample_rows(self, table: str, limit: int = 1000) -> list[dict[str, Any]]:
        return await self._query(f"SELECT * FROM `{self._ref(table)}` LIMIT {int(limit)}")

    async def stream_rows(self, table: str, chunk_size: int = 1000,
                          start_after: Any = None,
                          skip_rows: int = 0) -> AsyncIterator[list[dict[str, Any]]]:
        await self.connect()
        # list_rows pages natively via the BigQuery Storage/REST API.
        def _pages():
            return self.client.list_rows(self._ref(table), page_size=chunk_size).pages
        pages = await asyncio.to_thread(_pages)
        while True:
            page = await asyncio.to_thread(lambda: next(pages, None))
            if page is None:
                break
            yield [dict(r) for r in page]

    async def create_table(self, table: str, columns: list[dict[str, Any]],
                           primary_key: list[str] | None = None) -> None:
        from google.cloud import bigquery
        await self.connect()
        schema = [bigquery.SchemaField(
            c["name"], c["type"].upper() if c.get("type") else "STRING",
            mode="NULLABLE" if c.get("nullable", True) else "REQUIRED")
            for c in columns]
        t = bigquery.Table(self._ref(table), schema=schema)
        await asyncio.to_thread(self.client.create_table, t, True)  # exists_ok

    @staticmethod
    def _sanitize(value: Any) -> Any:
        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            return value.isoformat()
        if isinstance(value, decimal.Decimal):
            return float(value)
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str)
        return value

    async def insert_rows(self, table: str, rows: list[dict[str, Any]],
                          conflict_strategy: str = "fail") -> int:
        if not rows:
            return 0
        await self.connect()
        payload = [{k: self._sanitize(v) for k, v in r.items()} for r in rows]

        def _insert() -> int:
            # insert_rows_json is append-only; BigQuery has no unique constraints,
            # so every conflict strategy behaves as append.
            errors = self.client.insert_rows_json(self._ref(table), payload)
            if errors:
                raise RuntimeError(f"BigQuery insert errors: {errors[:3]}")
            return len(payload)
        return await asyncio.to_thread(_insert)

"""Abstract base connector every database driver implements."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class BaseConnector(ABC):
    """Uniform async interface over heterogeneous databases.

    Schema snapshot shape produced by get_schema():
    {
      "db_type": "postgres",
      "tables": {
        "<name>": {
          "columns": [{"name", "type", "nullable", "default", "primary_key"}],
          "primary_key": ["id"],
          "foreign_keys": [{"column", "ref_table", "ref_column"}],
          "indexes": [{"name", "columns", "unique"}],
          "row_count": 123
        }
      }
    }
    """

    db_type: str = "base"

    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def test_connection(self) -> bool: ...

    @abstractmethod
    async def get_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    async def count_rows(self, table: str) -> int: ...

    @abstractmethod
    async def sample_rows(self, table: str, limit: int = 1000) -> list[dict[str, Any]]: ...

    @abstractmethod
    def stream_rows(self, table: str, chunk_size: int = 1000,
                    start_after: Any = None,
                    skip_rows: int = 0) -> AsyncIterator[list[dict[str, Any]]]:
        """Yield rows in chunks, paginated by primary key — never the whole table.

        start_after / skip_rows resume a scan after a checkpoint so a restarted
        job never re-migrates committed rows. Connectors that cannot resume
        must ignore them and start from the beginning."""
        ...

    @abstractmethod
    async def create_table(self, table: str, columns: list[dict[str, Any]],
                           primary_key: list[str] | None = None) -> None:
        """columns: [{"name": str, "type": <target-native DDL type>, "nullable": bool}]"""
        ...

    @abstractmethod
    async def insert_rows(self, table: str, rows: list[dict[str, Any]],
                          conflict_strategy: str = "fail") -> int:
        """conflict_strategy: fail | skip | overwrite. Returns rows written."""
        ...

    async def drop_table(self, table: str) -> None:
        """Remove the target table/collection so a re-run starts clean.
        Connectors that cannot drop raise NotImplementedError — the executor
        logs a warning and proceeds."""
        raise NotImplementedError(f"{self.db_type} connector cannot drop tables")

    async def fetch_rows_by_key(self, table: str, key_column: str,
                                values: list[Any]) -> list[dict[str, Any]]:
        """Fetch rows whose key_column is in values. Generic fallback scans a
        bounded sample; SQL/Mongo connectors override with real key lookups."""
        wanted = set(values)
        return [r for r in await self.sample_rows(table, 5000)
                if r.get(key_column) in wanted]

    async def add_foreign_key(self, table: str, column: str,
                              ref_table: str, ref_column: str) -> None:
        """Recreate an FK constraint post-load. Optional per connector."""
        raise NotImplementedError(f"{self.db_type} connector cannot add FK constraints")

    async def __aenter__(self) -> "BaseConnector":
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

"""Streaming/batching helpers so large tables are never fully loaded in memory."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import psutil

DEFAULT_CHUNK_SIZE = 1000
MEMORY_CEILING_MB = 512


def memory_usage_mb() -> float:
    return psutil.Process().memory_info().rss / (1024 * 1024)


def memory_ok(ceiling_mb: int = MEMORY_CEILING_MB) -> bool:
    return memory_usage_mb() < ceiling_mb


async def rechunk(
    stream: AsyncIterator[list[dict[str, Any]]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> AsyncIterator[list[dict[str, Any]]]:
    """Re-batch an async stream of row lists into exact chunk_size batches."""
    buffer: list[dict[str, Any]] = []
    async for rows in stream:
        buffer.extend(rows)
        while len(buffer) >= chunk_size:
            yield buffer[:chunk_size]
            buffer = buffer[chunk_size:]
    if buffer:
        yield buffer

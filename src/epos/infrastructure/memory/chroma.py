"""Async boundary around a synchronous Chroma-style memory collection.

The concrete Chroma driver can implement ``SyncChromaMemoryCollection`` without
leaking the blocking client into the application event loop.
"""

import asyncio
from collections.abc import Sequence
from typing import Protocol

from epos.application.memory import LongTermMemoryRecord, MemoryError, MemoryHit, MemoryRecallQuery


class SyncChromaMemoryCollection(Protocol):
    """Small synchronous driver contract implemented by the concrete Chroma wrapper."""

    def add(self, record: LongTermMemoryRecord) -> None: ...

    def recall(self, query: MemoryRecallQuery, *, limit: int) -> Sequence[MemoryHit]: ...


class ChromaMemoryAdapter:
    def __init__(self, collection: SyncChromaMemoryCollection) -> None:
        self._collection = collection

    async def add(self, record: LongTermMemoryRecord) -> None:
        try:
            await asyncio.to_thread(self._collection.add, record)
        except Exception as exc:
            raise MemoryError(
                f"memory store failed: {type(exc).__name__}: {exc}",
                code="memory.store.failed",
            ) from exc

    async def recall(self, query: MemoryRecallQuery, *, limit: int) -> list[MemoryHit]:
        try:
            hits = await asyncio.to_thread(self._collection.recall, query, limit=limit)
        except Exception as exc:
            raise MemoryError(
                f"memory recall failed: {type(exc).__name__}: {exc}",
                code="memory.recall.failed",
            ) from exc
        return list(hits)

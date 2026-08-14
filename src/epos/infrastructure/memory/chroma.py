"""Async boundary around a synchronous Chroma-style memory collection.

The concrete Chroma driver can implement ``SyncChromaMemoryCollection`` without
leaking the blocking client into the application event loop.
"""

import asyncio
from collections.abc import Sequence
from typing import Protocol

from epos.application.memory import LongTermMemoryRecord, MemoryHit, MemoryRecallQuery


class SyncChromaMemoryCollection(Protocol):
    """Small synchronous driver contract implemented by the concrete Chroma wrapper."""

    def add(self, record: LongTermMemoryRecord) -> None: ...

    def recall(self, query: MemoryRecallQuery, *, limit: int) -> Sequence[MemoryHit]: ...


class ChromaMemoryAdapter:
    def __init__(self, collection: SyncChromaMemoryCollection) -> None:
        self._collection = collection

    async def add(self, record: LongTermMemoryRecord) -> None:
        await asyncio.to_thread(self._collection.add, record)

    async def recall(self, query: MemoryRecallQuery, *, limit: int) -> list[MemoryHit]:
        hits = await asyncio.to_thread(self._collection.recall, query, limit=limit)
        return list(hits)

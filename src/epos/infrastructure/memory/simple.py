"""Deterministic in-memory semantic adapter for tests and local fallback."""

import re

from epos.application.memory import LongTermMemoryRecord, MemoryHit, MemoryRecallQuery
from epos.domain.ids import EntityId


class SimpleMemoryAdapter:
    def __init__(self) -> None:
        self._records: dict[EntityId, list[LongTermMemoryRecord]] = {}

    async def add(self, record: LongTermMemoryRecord) -> None:
        self._records.setdefault(record.npc_id, []).append(record)

    async def recall(self, query: MemoryRecallQuery, *, limit: int) -> list[MemoryHit]:
        query_tokens = self._tokens(query.query_text)
        hits = [
            MemoryHit(
                memory=record.memory,
                semantic_score=self._similarity(query_tokens, self._tokens(record.memory.summary)),
            )
            for record in self._records.get(query.npc_id, [])
        ]
        hits.sort(
            key=lambda hit: (
                -hit.semantic_score,
                -int(hit.memory.turn),
                str(hit.memory.memory_id),
            )
        )
        return hits[: max(0, limit)]

    @staticmethod
    def _tokens(text: str) -> frozenset[str]:
        return frozenset(re.findall(r"\w+", text.casefold()))

    @staticmethod
    def _similarity(query: frozenset[str], memory: frozenset[str]) -> float:
        if not query or not memory:
            return 0.0
        overlap = len(query.intersection(memory))
        if overlap == 0:
            return 0.0
        return min(1.0, overlap / max(1, min(len(query), len(memory))))

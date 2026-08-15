"""NPC memory capture, recall and consolidation application services."""

from collections.abc import Sequence
from typing import Protocol

from pydantic import Field

from epos.application.ports import MemoryStorePort
from epos.domain.base import DomainModel
from epos.domain.errors import MemoryError
from epos.domain.ids import EntityId, MemoryId, TurnNumber
from epos.domain.memory import (
    EmotionalMemoryState,
    MemoryCapsuleState,
    MemoryEntryState,
    MemoryKind,
)
from epos.domain.npc import NPCState


class MemoryCapturePolicy(DomainModel):
    short_term_limit: int = Field(default=16, ge=1, le=20)


class MemoryService:
    def __init__(self, policy: MemoryCapturePolicy) -> None:
        self._policy = policy

    @classmethod
    def default(cls) -> "MemoryService":
        return cls(MemoryCapturePolicy())

    def remember(
        self,
        npc: NPCState,
        memory: MemoryEntryState,
        *,
        perceived: bool,
    ) -> NPCState:
        """Return a copied NPC state with a perceived memory recorded."""
        if not perceived:
            return npc

        updated = npc.model_copy(deep=True)
        if memory.kind is MemoryKind.CORE:
            updated.core_memories = (*updated.core_memories, memory)
            return updated

        if isinstance(memory, EmotionalMemoryState):
            updated.emotional_memory = (*updated.emotional_memory, memory)
            return updated

        recent = (*updated.short_term_memory, memory)
        updated.short_term_memory = recent[-self._policy.short_term_limit :]
        return updated


class LongTermMemoryRecord(DomainModel):
    npc_id: EntityId
    memory: MemoryEntryState


class MemoryRecallQuery(DomainModel):
    npc_id: EntityId
    player_input: str
    scene_context: str
    current_goals: tuple[str, ...] = ()
    current_turn: TurnNumber

    @property
    def query_text(self) -> str:
        parts = (self.player_input, self.scene_context, *self.current_goals)
        return " ".join(part.strip() for part in parts if part.strip())


class MemoryHit(DomainModel):
    memory: MemoryEntryState
    semantic_score: float = Field(ge=0.0, le=1.0)


class RankedMemory(DomainModel):
    memory: MemoryEntryState
    semantic_score: float = Field(ge=0.0, le=1.0)
    relevance_score: float = Field(ge=0.0, le=1.0)


class MemoryRecallResult(DomainModel):
    query_text: str
    memories: tuple[RankedMemory, ...]


class MemoryRecallService:
    def __init__(
        self,
        store: MemoryStorePort[LongTermMemoryRecord, MemoryRecallQuery, MemoryHit],
    ) -> None:
        self._store = store

    async def recall(self, query: MemoryRecallQuery, *, limit: int = 6) -> MemoryRecallResult:
        if limit < 1:
            raise ValueError("limit must be positive")

        raw_hits = await self._store.recall(query, limit=max(limit * 3, limit))
        ranked = tuple(sorted((self._rank(query, hit) for hit in raw_hits), key=self._key))[:limit]
        return MemoryRecallResult(query_text=query.query_text, memories=ranked)

    @staticmethod
    def _key(hit: RankedMemory) -> tuple[float, int, str]:
        return (-hit.relevance_score, -int(hit.memory.turn), str(hit.memory.memory_id))

    @staticmethod
    def _rank(query: MemoryRecallQuery, hit: MemoryHit) -> RankedMemory:
        age = max(0, int(query.current_turn) - int(hit.memory.turn))
        recency = 1.0 / (1.0 + age / 20.0)
        salience = hit.memory.salience / 10.0
        score = min(1.0, hit.semantic_score * 0.75 + salience * 0.15 + recency * 0.10)
        return RankedMemory(
            memory=hit.memory,
            semantic_score=hit.semantic_score,
            relevance_score=score,
        )


class MemorySummaryRequest(DomainModel):
    npc_id: EntityId
    memories: tuple[MemoryEntryState, ...]


class MemorySummaryDraft(DomainModel):
    summary: str
    themes: tuple[str, ...] = ()
    unresolved_threads: tuple[str, ...] = ()
    emotional_summary: str = ""


class MemorySummarizerPort(Protocol):
    """LLM-facing boundary. It summarizes only Python-selected memories."""

    async def summarize(self, request: MemorySummaryRequest) -> MemorySummaryDraft: ...


class ConsolidationPolicy(DomainModel):
    trigger_count: int = Field(default=24, ge=2)
    batch_size: int = Field(default=12, ge=2)
    min_age_turns: int = Field(default=20, ge=0)


class ConsolidationResult(DomainModel):
    capsule: MemoryCapsuleState
    original_memories: tuple[MemoryEntryState, ...]


_CRITICAL_TAGS = frozenset(
    {
        "promise",
        "betrayal",
        "confession",
        "secret_discovery",
        "irreversible_decision",
        "relationship_milestone",
    }
)


class MemoryConsolidationService:
    def __init__(self, *, summarizer: MemorySummarizerPort, policy: ConsolidationPolicy) -> None:
        self._summarizer = summarizer
        self._policy = policy

    async def consolidate(
        self,
        *,
        npc_id: EntityId,
        memories: Sequence[MemoryEntryState],
        current_turn: TurnNumber,
        capsule_id: MemoryId,
    ) -> ConsolidationResult | None:
        original = tuple(memories)
        eligible = tuple(
            sorted(
                (memory for memory in original if self._eligible(memory, current_turn)),
                key=lambda memory: (int(memory.turn), str(memory.memory_id)),
            )
        )
        if len(eligible) < self._policy.trigger_count:
            return None

        selected = eligible[: self._policy.batch_size]
        draft = await self._summarizer.summarize(
            MemorySummaryRequest(npc_id=npc_id, memories=selected)
        )
        capsule = MemoryCapsuleState(
            memory_id=capsule_id,
            turn=current_turn,
            summary=draft.summary,
            participants=self._participants(selected),
            salience=max(memory.salience for memory in selected),
            source_memory_ids=tuple(memory.memory_id for memory in selected),
            themes=draft.themes,
            unresolved_threads=draft.unresolved_threads,
            emotional_summary=draft.emotional_summary,
        )
        return ConsolidationResult(capsule=capsule, original_memories=original)

    def _eligible(self, memory: MemoryEntryState, current_turn: TurnNumber) -> bool:
        if memory.protected or memory.kind in {MemoryKind.CORE, MemoryKind.CAPSULE}:
            return False
        if _CRITICAL_TAGS.intersection(memory.tags):
            return False
        age = int(current_turn) - int(memory.turn)
        return age >= self._policy.min_age_turns

    @staticmethod
    def _participants(memories: Sequence[MemoryEntryState]) -> tuple[EntityId, ...]:
        result: list[EntityId] = []
        seen: set[EntityId] = set()
        for memory in memories:
            for participant in memory.participants:
                if participant not in seen:
                    seen.add(participant)
                    result.append(participant)
        return tuple(result)


__all__ = [
    "ConsolidationPolicy",
    "ConsolidationResult",
    "LongTermMemoryRecord",
    "MemoryCapturePolicy",
    "MemoryConsolidationService",
    "MemoryError",
    "MemoryHit",
    "MemoryRecallQuery",
    "MemoryRecallResult",
    "MemoryRecallService",
    "MemoryService",
    "MemorySummarizerPort",
    "MemorySummaryDraft",
    "MemorySummaryRequest",
    "RankedMemory",
]

"""Persistent NPC memory contracts.

Long-term archives live behind application ports; only bounded active memory layers
belong directly to NPC state.
"""

from enum import StrEnum

from pydantic import Field

from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, MemoryId, TurnNumber


class MemoryKind(StrEnum):
    EPISODIC = "episodic"
    CORE = "core"
    EMOTIONAL = "emotional"
    CAPSULE = "capsule"


class MemoryEntryState(DomainModel):
    memory_id: MemoryId
    turn: TurnNumber
    summary: str
    participants: tuple[EntityId, ...] = ()
    salience: float = Field(default=0.0, ge=0.0, le=10.0)
    kind: MemoryKind = MemoryKind.EPISODIC
    protected: bool = False
    tags: tuple[str, ...] = ()


class EmotionalMemoryState(MemoryEntryState):
    kind: MemoryKind = MemoryKind.EMOTIONAL
    emotion: str
    intensity: float = Field(ge=0.0, le=10.0)


class MemoryCapsuleState(MemoryEntryState):
    kind: MemoryKind = MemoryKind.CAPSULE
    source_memory_ids: tuple[MemoryId, ...]
    themes: tuple[str, ...] = ()
    unresolved_threads: tuple[str, ...] = ()
    emotional_summary: str = ""

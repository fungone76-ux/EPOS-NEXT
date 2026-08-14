"""Minimal persisted memory records; retrieval behavior belongs to Module 04."""

from pydantic import Field

from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, MemoryId, TurnNumber


class MemoryEntryState(DomainModel):
    memory_id: MemoryId
    turn: TurnNumber
    summary: str
    participants: tuple[EntityId, ...] = ()


class EmotionalMemoryState(MemoryEntryState):
    emotion: str
    intensity: float = Field(ge=0.0, le=10.0)

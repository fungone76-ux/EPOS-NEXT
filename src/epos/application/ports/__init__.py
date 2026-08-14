"""Dependency-inversion ports for EPOS NEXT infrastructure."""

from collections.abc import Sequence
from typing import Protocol, TypeVar

from epos.domain.ids import SessionId

LLMRequestT = TypeVar("LLMRequestT", contravariant=True)
LLMResponseT = TypeVar("LLMResponseT", covariant=True)
RenderRequestT = TypeVar("RenderRequestT", contravariant=True)
RenderResponseT = TypeVar("RenderResponseT", covariant=True)
StateT = TypeVar("StateT")
MemoryRecordT = TypeVar("MemoryRecordT", contravariant=True)
MemoryQueryT = TypeVar("MemoryQueryT", contravariant=True)
MemoryHitT = TypeVar("MemoryHitT", covariant=True)
EventT = TypeVar("EventT", contravariant=True)


class LLMPort(Protocol[LLMRequestT, LLMResponseT]):
    """Asynchronous language-model boundary."""

    async def invoke(self, request: LLMRequestT) -> LLMResponseT: ...


class RendererPort(Protocol[RenderRequestT, RenderResponseT]):
    """Asynchronous render backend boundary."""

    async def render(self, request: RenderRequestT) -> RenderResponseT: ...


class StateStorePort(Protocol[StateT]):
    """Asynchronous authoritative-state persistence boundary."""

    async def load(self, session_id: SessionId) -> StateT: ...

    async def save(self, session_id: SessionId, state: StateT) -> None: ...


class MemoryStorePort(Protocol[MemoryRecordT, MemoryQueryT, MemoryHitT]):
    """Asynchronous semantic-memory storage boundary."""

    async def add(self, record: MemoryRecordT) -> None: ...

    async def recall(self, query: MemoryQueryT, *, limit: int) -> Sequence[MemoryHitT]: ...


class EventBusPort(Protocol[EventT]):
    """Asynchronous domain/application event publication boundary."""

    async def publish(self, event: EventT) -> None: ...


class EmbeddingPort(Protocol):
    """Asynchronous batch embedding boundary."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


__all__ = [
    "EmbeddingPort",
    "EventBusPort",
    "LLMPort",
    "MemoryStorePort",
    "RendererPort",
    "StateStorePort",
]

"""Runtime health and diagnostic contracts shared by all presentation adapters."""

from __future__ import annotations

from typing import Literal

from epos.domain.base import DomainModel
from epos.domain.ids import SessionId, WorldpackId


class ComponentHealthView(DomainModel):
    status: Literal["up", "down", "degraded", "unknown"]
    detail: str | None = None


class RuntimeHealthView(DomainModel):
    llm: ComponentHealthView
    renderer: ComponentHealthView
    current_worldpack: WorldpackId | None = None
    current_session: SessionId | None = None


class CacheStats(DomainModel):
    exact_hits: int = 0
    semantic_hits: int = 0
    misses: int = 0
    writes: int = 0

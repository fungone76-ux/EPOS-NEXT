"""Ports for durable pending renders and backend-specific snapshot replay."""

from __future__ import annotations

from typing import Protocol

from epos.application.visual.recovery.models import PendingRender
from epos.application.visual.rendering import RenderResult
from epos.domain.ids import SessionId, TurnNumber


class PendingRenderStorePort(Protocol):
    async def save(self, pending: PendingRender) -> str: ...

    async def load(self, session_id: SessionId) -> PendingRender | None: ...

    async def delete(self, session_id: SessionId, turn_number: TurnNumber) -> None: ...


class PendingRenderExecutorPort(Protocol):
    async def render(self, pending: PendingRender) -> RenderResult: ...

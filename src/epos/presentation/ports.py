"""Application facade shared by desktop and HTTP presentation layers."""

from __future__ import annotations

from typing import Protocol

from epos.application.diagnostics import RuntimeHealthView
from epos.application.results import TurnResult, TurnVisualResult
from epos.application.turn import TurnCommand
from epos.domain.ids import SessionId, WorldpackId
from epos.presentation.models import SessionView, WorldpackView


class EPOSRuntimePort(Protocol):
    async def create_session(self, worldpack_id: WorldpackId) -> SessionView: ...

    async def get_session(self, session_id: SessionId) -> SessionView: ...

    async def run_turn(self, session_id: SessionId, command: TurnCommand) -> TurnResult: ...

    async def advance(self, session_id: SessionId) -> SessionView: ...

    async def resume(self, session_id: SessionId) -> SessionView: ...

    async def rerender(self, session_id: SessionId) -> TurnVisualResult: ...

    async def list_worldpacks(self) -> tuple[WorldpackView, ...]: ...

    async def health(self) -> RuntimeHealthView: ...

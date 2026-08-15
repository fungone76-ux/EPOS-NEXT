"""Health probes and runtime identity ports."""

from __future__ import annotations

from typing import Protocol

from epos.application.diagnostics.models import ComponentHealthView
from epos.domain.ids import SessionId, WorldpackId


class ComponentHealthProbePort(Protocol):
    async def check(self) -> ComponentHealthView: ...


class RuntimeIdentityPort(Protocol):
    def current_worldpack(self) -> WorldpackId | None: ...

    def current_session(self) -> SessionId | None: ...

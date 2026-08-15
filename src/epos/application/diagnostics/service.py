"""Aggregate typed health without leaking provider exceptions across presentation."""

from __future__ import annotations

import asyncio

from epos.application.diagnostics.models import ComponentHealthView, RuntimeHealthView
from epos.application.diagnostics.ports import (
    ComponentHealthProbePort,
    RuntimeIdentityPort,
)


class RuntimeDiagnosticsService:
    def __init__(
        self,
        *,
        llm: ComponentHealthProbePort,
        renderer: ComponentHealthProbePort,
        identity: RuntimeIdentityPort,
    ) -> None:
        self._llm = llm
        self._renderer = renderer
        self._identity = identity

    async def health(self) -> RuntimeHealthView:
        llm, renderer = await asyncio.gather(
            self._safe_check(self._llm),
            self._safe_check(self._renderer),
        )
        return RuntimeHealthView(
            llm=llm,
            renderer=renderer,
            current_worldpack=self._identity.current_worldpack(),
            current_session=self._identity.current_session(),
        )

    @staticmethod
    async def _safe_check(probe: ComponentHealthProbePort) -> ComponentHealthView:
        try:
            return await probe.check()
        except Exception as exc:
            return ComponentHealthView(
                status="down",
                detail=f"{type(exc).__name__}: {exc}",
            )

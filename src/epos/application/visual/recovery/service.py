"""Retry an already-prepared render without replaying narrative work."""

from __future__ import annotations

from epos.application.visual.recovery.models import RetryImageResult
from epos.application.visual.recovery.ports import (
    PendingRenderExecutorPort,
    PendingRenderStorePort,
)
from epos.domain.errors import EposValidationError
from epos.domain.ids import SessionId


class PendingRenderNotFoundError(EposValidationError):
    def __init__(self, session_id: SessionId) -> None:
        super().__init__(
            f"no pending render for session {session_id}",
            code="visual.pending_render_not_found",
        )


class RenderRecoveryService:
    def __init__(
        self,
        *,
        store: PendingRenderStorePort,
        executor: PendingRenderExecutorPort,
    ) -> None:
        self._store = store
        self._executor = executor

    async def retry(self, session_id: SessionId) -> RetryImageResult:
        pending = await self._store.load(session_id)
        if pending is None:
            raise PendingRenderNotFoundError(session_id)

        result = await self._executor.render(pending)
        if result.status == "success":
            await self._store.delete(pending.session_id, pending.turn_number)
        return RetryImageResult(pending=pending, render_result=result)

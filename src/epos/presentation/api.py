"""FastAPI adapter for the shared EPOS runtime facade."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import TypeVar

from fastapi import FastAPI, HTTPException
from pydantic import Field

from epos.application.diagnostics import ComponentHealthView, RuntimeHealthView
from epos.application.recovery import ErrorRecoveryPolicy
from epos.application.results import TurnResult, TurnVisualResult
from epos.application.turn import CheckDecision, TurnCommand
from epos.domain.base import DomainModel
from epos.domain.errors import EposError
from epos.domain.ids import LocationId, SessionId, WorldpackId
from epos.presentation.models import SessionView, WorldpackView
from epos.presentation.ports import EPOSRuntimePort

T = TypeVar("T")


class CreateSessionRequest(DomainModel):
    worldpack_id: WorldpackId


class TurnRequest(DomainModel):
    player_input: str = Field(min_length=1)
    known_location_ids: tuple[LocationId, ...] = ()
    check_decision: CheckDecision | None = None

    def command(self) -> TurnCommand:
        return TurnCommand(
            player_input=self.player_input,
            known_location_ids=self.known_location_ids,
            check_decision=self.check_decision,
        )


def create_app(runtime: EPOSRuntimePort) -> FastAPI:
    app = FastAPI(title="EPOS NEXT Debug API", version="1.0")
    recovery = ErrorRecoveryPolicy()

    async def invoke(operation: Awaitable[T]) -> T:
        try:
            return await operation
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"resource not found: {exc}") from exc
        except EposError as exc:
            decision = recovery.decide(exc, phase="api")
            raise HTTPException(
                status_code=decision.http_status,
                detail={
                    "code": decision.code,
                    "message": decision.message,
                    "error_type": decision.error_type,
                    "recovery_action": decision.action.value,
                    "retryable": decision.retryable,
                    "committed_state_preserved": decision.committed_state_preserved,
                },
            ) from exc

    @app.post("/sessions", response_model=SessionView)
    async def create_session(request: CreateSessionRequest) -> SessionView:
        return await invoke(runtime.create_session(request.worldpack_id))

    @app.get("/sessions/{session_id}", response_model=SessionView)
    async def get_session(session_id: str) -> SessionView:
        return await invoke(runtime.get_session(SessionId(session_id)))

    @app.post("/sessions/{session_id}/turns", response_model=TurnResult)
    async def run_turn(session_id: str, request: TurnRequest) -> TurnResult:
        return await invoke(runtime.run_turn(SessionId(session_id), request.command()))

    @app.post("/sessions/{session_id}/advance", response_model=SessionView)
    async def advance(session_id: str) -> SessionView:
        return await invoke(runtime.advance(SessionId(session_id)))

    @app.post("/sessions/{session_id}/resume", response_model=SessionView)
    async def resume(session_id: str) -> SessionView:
        return await invoke(runtime.resume(SessionId(session_id)))

    @app.post("/sessions/{session_id}/rerender", response_model=TurnVisualResult)
    async def rerender(session_id: str) -> TurnVisualResult:
        return await invoke(runtime.rerender(SessionId(session_id)))

    @app.get("/worldpacks", response_model=list[WorldpackView])
    async def worldpacks() -> tuple[WorldpackView, ...]:
        return await invoke(runtime.list_worldpacks())

    @app.get("/health", response_model=RuntimeHealthView)
    async def health() -> RuntimeHealthView:
        return await invoke(runtime.health())

    @app.get("/health/llm", response_model=ComponentHealthView)
    async def health_llm() -> ComponentHealthView:
        return (await invoke(runtime.health())).llm

    @app.get("/health/renderer", response_model=ComponentHealthView)
    async def health_renderer() -> ComponentHealthView:
        return (await invoke(runtime.health())).renderer

    return app

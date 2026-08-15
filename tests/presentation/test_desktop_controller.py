from __future__ import annotations

import pytest

from epos.application.results import (
    TurnDiagnostics,
    TurnGameResult,
    TurnResult,
    TurnVisualResult,
)
from epos.domain.ids import LocationId, SceneId, SessionId, TurnNumber, WorldpackId
from epos.presentation import (
    ComponentHealthView,
    DesktopController,
    RuntimeHealthView,
    SessionView,
)


def _session(turn: int) -> SessionView:
    return SessionView(
        session_id=SessionId("session-1"),
        turn_number=TurnNumber(turn),
        worldpack_id=WorldpackId("resort-world"),
        location_id=LocationId("lobby"),
        location_name="Lobby",
        day=1,
        world_phase="evening",
    )


def _health() -> RuntimeHealthView:
    return RuntimeHealthView(
        llm=ComponentHealthView(status="up"),
        renderer=ComponentHealthView(status="down", detail="offline"),
        current_worldpack=WorldpackId("resort-world"),
        current_session=SessionId("session-1"),
    )


def _visual(*, success: bool) -> TurnVisualResult:
    return TurnVisualResult(
        vst_status="ok",
        image_path="renders/retry.png" if success else None,
        render_status="success" if success else "failed",
        render_error=None if success else "offline",
        retry_available=not success,
    )


class FakeRuntime:
    def __init__(self) -> None:
        self.turn = 1
        self.inputs: list[str] = []

    async def get_session(self, session_id):
        return _session(self.turn)

    async def health(self):
        return _health()

    async def run_turn(self, session_id, command):
        self.inputs.append(command.player_input)
        self.turn += 1
        return TurnResult(
            session_id=SessionId("session-1"),
            turn_number=TurnNumber(self.turn),
            narration="Luna sorride.",
            game=TurnGameResult(outcome="no_check"),
            visual=_visual(success=False),
            diagnostics=TurnDiagnostics(scene_id=SceneId(f"session-1:{self.turn}")),
        )

    async def rerender(self, session_id):
        return _visual(success=True)


@pytest.mark.asyncio
async def test_desktop_controller_updates_three_panels_from_one_public_result() -> None:
    runtime = FakeRuntime()
    controller = DesktopController(runtime)
    await controller.initialize(SessionId("session-1"))

    view = await controller.submit_player_input("Saluto Luna")

    assert runtime.inputs == ["Saluto Luna"]
    assert int(view.session.turn_number) == 2
    assert view.story.narration == "Luna sorride."
    assert view.visual.result is not None
    assert view.visual.result.render_status == "failed"
    assert view.health.llm.status == "up"


@pytest.mark.asyncio
async def test_retry_image_updates_only_visual_panel() -> None:
    controller = DesktopController(FakeRuntime())
    await controller.initialize(SessionId("session-1"))
    before = await controller.submit_player_input("Osservo")

    after = await controller.retry_image()

    assert after.session == before.session
    assert after.story == before.story
    assert after.visual.current_image == "renders/retry.png"
    assert after.visual.result is not None
    assert after.visual.result.render_status == "success"

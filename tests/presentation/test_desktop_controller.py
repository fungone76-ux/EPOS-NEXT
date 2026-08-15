from __future__ import annotations

import pytest

from epos.application.results import (
    TurnDiagnostics,
    TurnGameResult,
    TurnResult,
    TurnVisualResult,
)
from epos.application.turn import CheckDecision
from epos.domain.ids import LocationId, SceneId, SessionId, TurnNumber, WorldpackId
from epos.presentation import (
    ComponentHealthView,
    DesktopController,
    MissionView,
    PlayerSkillView,
    PlayerView,
    PresentNPCView,
    RuntimeHealthView,
    SessionView,
)
from epos.presentation.desktop import session_state_html, visual_debug_text
from epos.presentation.models import VisualPanelState


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
        self.check_decisions: list[CheckDecision | None] = []

    async def get_session(self, session_id):
        return _session(self.turn)

    async def create_session(self, worldpack_id):
        self.turn = 1
        return _session(self.turn).model_copy(
            update={"session_id": SessionId("session-new")}
        )

    async def resume(self, session_id):
        return _session(self.turn)

    async def health(self):
        return _health()

    async def run_turn(self, session_id, command):
        self.inputs.append(command.player_input)
        self.check_decisions.append(command.check_decision)
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
async def test_desktop_controller_forwards_the_players_explicit_check_decision() -> None:
    runtime = FakeRuntime()
    controller = DesktopController(runtime)
    await controller.initialize(SessionId("session-1"))

    await controller.submit_player_input(
        "Convincila",
        check_decision=CheckDecision.ROLL,
    )

    assert runtime.check_decisions == [CheckDecision.ROLL]


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


@pytest.mark.asyncio
async def test_controller_can_create_and_resume_sessions_without_touching_runtime_details() -> None:
    controller = DesktopController(FakeRuntime())
    await controller.initialize(SessionId("session-1"))

    created = await controller.new_session()
    resumed = await controller.resume_session()

    assert created.session.session_id == SessionId("session-new")
    assert resumed.session.worldpack_id == WorldpackId("resort-world")


def test_original_style_state_panel_is_readable_and_contains_no_raw_json() -> None:
    session = _session(3).model_copy(
        update={
            "player": PlayerView(
                entity_id="player",
                name="Enrico",
                inventory=("chiave",),
                outfit=("camicia", "pantaloni"),
            ),
            "present_npcs": (
                PresentNPCView(
                    entity_id="luna",
                    name="Luna",
                    role="hostess",
                    outfit=("abito rosso",),
                ),
            ),
            "player_skills": (
                PlayerSkillView(skill_id="charm", name="Fascino", rating=2),
            ),
            "missions": (MissionView(mission_id="welcome", status="active"),),
        }
    )

    rendered = session_state_html(session)

    assert "SITUAZIONE" in rendered
    assert "Luna" in rendered
    assert "abito rosso" in rendered
    assert "Fascino" in rendered
    assert "{" not in rendered


def test_visual_debug_is_prompt_oriented_instead_of_raw_result_json() -> None:
    visual = _visual(success=False).model_copy(
        update={"positive_prompt": "Luna at the resort", "backend": "a1111"}
    )

    rendered = visual_debug_text(VisualPanelState(result=visual))

    assert "PROMPT POSITIVO" in rendered
    assert "Luna at the resort" in rendered
    assert "Backend: a1111" in rendered

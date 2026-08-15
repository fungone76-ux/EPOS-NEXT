from __future__ import annotations

from fastapi.testclient import TestClient

from epos.application.results import (
    TurnDiagnostics,
    TurnGameResult,
    TurnResult,
    TurnVisualResult,
)
from epos.domain.ids import LocationId, SceneId, SessionId, TurnNumber, WorldpackId
from epos.presentation import (
    ComponentHealthView,
    RuntimeHealthView,
    SessionView,
    WorldpackView,
    create_app,
)


def _session(session_id: str = "session-1", turn: int = 1) -> SessionView:
    return SessionView(
        session_id=SessionId(session_id),
        turn_number=TurnNumber(turn),
        worldpack_id=WorldpackId("resort-world"),
        location_id=LocationId("lobby"),
        location_name="Lobby",
        day=1,
        world_phase="evening",
    )


def _visual() -> TurnVisualResult:
    return TurnVisualResult(
        vst_status="ok",
        image_path="renders/turn.png",
        render_status="success",
        retry_available=False,
    )


class FakeRuntime:
    def __init__(self) -> None:
        self.commands = []

    async def create_session(self, worldpack_id):
        assert worldpack_id == WorldpackId("resort-world")
        return _session()

    async def get_session(self, session_id):
        if session_id == SessionId("missing"):
            raise KeyError(session_id)
        return _session(str(session_id))

    async def run_turn(self, session_id, command):
        self.commands.append(command)
        return TurnResult(
            session_id=session_id,
            turn_number=TurnNumber(2),
            narration="Turno completato.",
            game=TurnGameResult(outcome="no_check"),
            visual=_visual(),
            diagnostics=TurnDiagnostics(scene_id=SceneId(f"{session_id}:2")),
        )

    async def advance(self, session_id):
        return _session(str(session_id), 2)

    async def resume(self, session_id):
        return _session(str(session_id), 1)

    async def rerender(self, session_id):
        return _visual()

    async def list_worldpacks(self):
        return (WorldpackView(worldpack_id=WorldpackId("resort-world"), title="Resort"),)

    async def health(self):
        return RuntimeHealthView(
            llm=ComponentHealthView(status="up"),
            renderer=ComponentHealthView(status="up"),
            current_worldpack=WorldpackId("resort-world"),
            current_session=SessionId("session-1"),
        )


def test_debug_api_exposes_session_turn_rerender_and_health_contracts() -> None:
    runtime = FakeRuntime()
    client = TestClient(create_app(runtime))

    assert client.post("/sessions", json={"worldpack_id": "resort-world"}).status_code == 200
    assert client.get("/sessions/session-1").json()["location_name"] == "Lobby"
    turn = client.post(
        "/sessions/session-1/turns",
        json={"player_input": "Saluto Luna"},
    )
    assert turn.status_code == 200
    assert turn.json()["narration"] == "Turno completato."
    assert runtime.commands[0].player_input == "Saluto Luna"
    assert client.post("/sessions/session-1/advance").json()["turn_number"] == 2
    assert client.post("/sessions/session-1/resume").status_code == 200
    assert client.post("/sessions/session-1/rerender").json()["render_status"] == "success"
    assert client.get("/worldpacks").json()[0]["worldpack_id"] == "resort-world"
    assert client.get("/health").json()["llm"]["status"] == "up"
    assert client.get("/health/llm").json()["status"] == "up"
    assert client.get("/health/renderer").json()["status"] == "up"


def test_debug_api_maps_missing_session_to_not_found() -> None:
    client = TestClient(create_app(FakeRuntime()))

    response = client.get("/sessions/missing")

    assert response.status_code == 404
    assert "resource not found" in response.json()["detail"]

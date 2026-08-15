from __future__ import annotations

import pytest

from epos.application.visual.bridge import RenderRequestSnapshot
from epos.application.visual.canonical import (
    CanonicalAction,
    CanonicalCamera,
    CanonicalLocation,
    CanonicalVisualFocus,
    CanonicalVST,
    ResolvedSemanticEntry,
)
from epos.application.visual.models import SceneTime
from epos.application.visual.prompt import RenderPromptContract
from epos.application.visual.recovery import PendingRender, RenderRecoveryService
from epos.application.visual.rendering import RenderResult
from epos.application.visual.vst import (
    SemanticIntent,
    VSTLightingIntent,
    VSTSafetyIntent,
    VSTStyleIntent,
)
from epos.domain.ids import LocationId, SceneId, SessionId, TurnNumber, WorldpackId
from epos.infrastructure.persistence import JsonPendingRenderStore


def _pending() -> PendingRender:
    scene_id = SceneId("session-1:12")
    canonical = CanonicalVST(
        scene_id=scene_id,
        worldpack_id=WorldpackId("resort-world"),
        time=SceneTime(turn_number=TurnNumber(12), day=1, world_phase="evening"),
        location=CanonicalLocation(location_id=LocationId("suite"), name="Suite"),
        subjects=(),
        action=CanonicalAction(
            semantic=ResolvedSemanticEntry(entry_id="standing", description="standing")
        ),
        visual_focus=CanonicalVisualFocus(
            subject_ids=(),
            intent=SemanticIntent(description="scene"),
        ),
        camera=CanonicalCamera(
            semantic=ResolvedSemanticEntry(entry_id="medium", description="medium shot")
        ),
        lighting=VSTLightingIntent(intent=SemanticIntent(description="warm light")),
        style=VSTStyleIntent(intent=SemanticIntent(description="realistic")),
        safety=VSTSafetyIntent(),
    )
    return PendingRender(
        session_id=SessionId("session-1"),
        turn_number=TurnNumber(12),
        scene_id=scene_id,
        canonical_vst=canonical,
        prompt_contract=RenderPromptContract(
            positive_prompt="canonical positive",
            negative_prompt="fixed negative",
            width=896,
            height=1152,
        ),
        render_request=RenderRequestSnapshot(
            backend="comfyui",
            request_id="request-12",
            payload={"client_id": "epos", "prompt": {}},
        ),
    )


class MemoryPendingStore:
    def __init__(self, pending: PendingRender) -> None:
        self.pending = pending
        self.deleted = False

    async def save(self, pending: PendingRender) -> str:
        self.pending = pending
        return "memory"

    async def load(self, session_id: SessionId) -> PendingRender | None:
        assert session_id == self.pending.session_id
        return None if self.deleted else self.pending

    async def delete(self, session_id: SessionId, turn_number: TurnNumber) -> None:
        assert session_id == self.pending.session_id
        assert turn_number == self.pending.turn_number
        self.deleted = True


class RecordingExecutor:
    def __init__(self, result: RenderResult) -> None:
        self.result = result
        self.calls: list[PendingRender] = []

    async def render(self, pending: PendingRender) -> RenderResult:
        self.calls.append(pending)
        return self.result


def _result(status: str) -> RenderResult:
    if status == "success":
        return RenderResult(
            status="success",
            image_path="renders/retry-12.png",
            backend="comfyui",
            prompt_id="retry-12",
            error=None,
            duration_ms=80,
            attempts=1,
        )
    return RenderResult(
        status="failed",
        image_path=None,
        backend="comfyui",
        prompt_id=None,
        error="still offline",
        duration_ms=10,
        attempts=1,
    )


@pytest.mark.asyncio
async def test_retry_replays_only_saved_render_contract_and_clears_on_success() -> None:
    pending = _pending()
    store = MemoryPendingStore(pending)
    executor = RecordingExecutor(_result("success"))
    service = RenderRecoveryService(store=store, executor=executor)

    retried = await service.retry(SessionId("session-1"))

    assert executor.calls == [pending]
    assert retried.render_result.status == "success"
    assert store.deleted is True


@pytest.mark.asyncio
async def test_failed_retry_keeps_pending_contract_for_another_attempt() -> None:
    store = MemoryPendingStore(_pending())
    service = RenderRecoveryService(store=store, executor=RecordingExecutor(_result("failed")))

    retried = await service.retry(SessionId("session-1"))

    assert retried.render_result.status == "failed"
    assert store.deleted is False


@pytest.mark.asyncio
async def test_pending_render_json_round_trip_is_atomic_and_exact(tmp_path) -> None:
    store = JsonPendingRenderStore(tmp_path)
    pending = _pending()

    path = await store.save(pending)
    restored = await store.load(pending.session_id)

    assert path.endswith("session-1.pending-render.json")
    assert restored == pending
    await store.delete(pending.session_id, pending.turn_number)
    assert await store.load(pending.session_id) is None

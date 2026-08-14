from __future__ import annotations

import json
from pathlib import Path

import pytest

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
from epos.application.visual.rendering import RenderResult
from epos.application.visual.vst import (
    RawVST,
    SemanticIntent,
    VSTActionIntent,
    VSTCameraIntent,
    VSTLightingIntent,
    VSTLocationIntent,
    VSTSafetyIntent,
    VSTStyleIntent,
    VSTSubjectIntent,
    VSTSubjectProminence,
    VSTVisualFocus,
)
from epos.application.visual.workflow import ComfyWorkflowRequest
from epos.domain.ids import EntityId, LocationId, SceneId, WorldpackId


def _raw_vst() -> RawVST:
    victoria = EntityId("victoria")
    return RawVST(
        scene_id=SceneId("session:12"),
        location=VSTLocationIntent(location_id=LocationId("pool")),
        subjects=(
            VSTSubjectIntent(
                entity_id=victoria,
                prominence=VSTSubjectProminence.PRIMARY,
            ),
        ),
        action=VSTActionIntent(
            participants=(victoria,),
            intent=SemanticIntent(description="conversation beside pool"),
        ),
        visual_focus=VSTVisualFocus(
            subject_ids=(victoria,),
            intent=SemanticIntent(description="focus on Victoria"),
        ),
        camera=VSTCameraIntent(shot=SemanticIntent(description="medium shot")),
        lighting=VSTLightingIntent(
            intent=SemanticIntent(description="warm sunset light")
        ),
        style=VSTStyleIntent(intent=SemanticIntent(description="cinematic realism")),
        safety=VSTSafetyIntent(),
    )


def _canonical_vst() -> CanonicalVST:
    return CanonicalVST(
        scene_id=SceneId("session:12"),
        worldpack_id=WorldpackId("resort-world"),
        time=SceneTime(turn_number=12, day=1, world_phase="sunset"),
        location=CanonicalLocation(location_id=LocationId("pool"), name="Pool"),
        subjects=(),
        action=CanonicalAction(
            participants=(),
            semantic=ResolvedSemanticEntry(
                entry_id="pool_conversation",
                description="conversation beside pool",
                positive_fragment="conversation beside the pool",
            ),
        ),
        visual_focus=CanonicalVisualFocus(
            subject_ids=(),
            intent=SemanticIntent(description="scene focus"),
        ),
        camera=CanonicalCamera(
            semantic=ResolvedSemanticEntry(
                entry_id="medium_shot",
                description="medium shot",
                positive_fragment="medium shot",
            )
        ),
        lighting=VSTLightingIntent(
            intent=SemanticIntent(description="warm sunset light")
        ),
        style=VSTStyleIntent(intent=SemanticIntent(description="cinematic realism")),
        safety=VSTSafetyIntent(),
    )


def _snapshot(*, rendered: bool):
    from epos.application.visual.bridge import VisualPipelineDiagnostics

    return VisualPipelineDiagnostics(
        phase="rendered" if rendered else "prepared",
        scene_id=SceneId("session:12"),
        raw_vst=_raw_vst(),
        canonical_vst=_canonical_vst(),
        prompt_contract=RenderPromptContract(
            positive_prompt="canonical positive",
            negative_prompt="fixed negative",
            checkpoint="model.safetensors",
            width=896,
            height=1152,
        ),
        workflow_request=ComfyWorkflowRequest(
            prompt={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
            client_id="client-1",
        ),
        render_result=(
            RenderResult(
                status="success",
                image_path="renders/job-1.png",
                backend="comfyui",
                prompt_id="job-1",
                error=None,
                duration_ms=50,
                attempts=1,
            )
            if rendered
            else None
        ),
    )


@pytest.mark.asyncio
async def test_atomic_visual_diagnostics_store_writes_deterministic_scene_file(
    tmp_path: Path,
) -> None:
    from epos.infrastructure.rendering.visual_diagnostics import (
        AtomicVisualDiagnosticsStore,
    )

    store = AtomicVisualDiagnosticsStore(tmp_path)
    target = await store.save(_snapshot(rendered=False))

    path = Path(target)
    assert path == tmp_path / "session_12.visual.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["phase"] == "prepared"
    assert payload["prompt_contract"]["positive_prompt"] == "canonical positive"
    assert payload["prompt_contract"]["negative_prompt"] == "fixed negative"
    assert payload["workflow_request"]["client_id"] == "client-1"
    assert payload["render_result"] is None


@pytest.mark.asyncio
async def test_final_diagnostics_atomically_replace_prepared_snapshot(tmp_path: Path) -> None:
    from epos.infrastructure.rendering.visual_diagnostics import (
        AtomicVisualDiagnosticsStore,
    )

    store = AtomicVisualDiagnosticsStore(tmp_path)
    first = await store.save(_snapshot(rendered=False))
    second = await store.save(_snapshot(rendered=True))

    assert first == second
    payload = json.loads(Path(second).read_text(encoding="utf-8"))
    assert payload["phase"] == "rendered"
    assert payload["render_result"]["status"] == "success"
    assert payload["render_result"]["prompt_id"] == "job-1"


@pytest.mark.asyncio
async def test_diagnostics_store_wraps_filesystem_failure(tmp_path: Path) -> None:
    from epos.application.visual.bridge import VisualDiagnosticsPersistenceError
    from epos.infrastructure.rendering.visual_diagnostics import (
        AtomicVisualDiagnosticsStore,
    )

    blocker = tmp_path / "not-a-directory"
    blocker.write_text("file", encoding="utf-8")
    store = AtomicVisualDiagnosticsStore(blocker)

    with pytest.raises(VisualDiagnosticsPersistenceError, match="visual diagnostics"):
        await store.save(_snapshot(rendered=False))

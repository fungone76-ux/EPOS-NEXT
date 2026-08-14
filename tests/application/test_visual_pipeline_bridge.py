from __future__ import annotations

from collections.abc import Callable

import pytest

from epos.application.visual.canonical import CanonicalVST
from epos.application.visual.models import ObservableSceneState
from epos.application.visual.prompt import PromptCompilerProfile, RenderPromptContract
from epos.application.visual.rendering import RenderResult
from epos.application.visual.vst import RawVST
from epos.application.visual.workflow import (
    ComfyWorkflowBuildParameters,
    ComfyWorkflowProfile,
    ComfyWorkflowRequest,
    ComfyWorkflowTemplate,
)
from epos.application.worldpacks.models import LoadedWorldpack
from epos.domain.ids import SceneId


def _scene() -> ObservableSceneState:
    return ObservableSceneState.model_construct(scene_id=SceneId("session:12"))


def _raw() -> RawVST:
    return RawVST.model_construct(scene_id=SceneId("session:12"))


def _canonical() -> CanonicalVST:
    return CanonicalVST.model_construct(scene_id=SceneId("session:12"))


def _worldpack() -> LoadedWorldpack:
    return LoadedWorldpack.model_construct()


def _prompt_contract() -> RenderPromptContract:
    return RenderPromptContract(
        positive_prompt="canonical positive",
        negative_prompt="fixed negative",
        checkpoint="model.safetensors",
        width=896,
        height=1152,
        sampler="dpmpp_2m",
        scheduler="normal",
        steps=24,
        cfg=7.0,
    )


def _workflow_request() -> ComfyWorkflowRequest:
    return ComfyWorkflowRequest(
        prompt={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
        client_id="epos-session-12",
    )


def _render_success() -> RenderResult:
    return RenderResult(
        status="success",
        image_path="renders/job-1.png",
        backend="comfyui",
        prompt_id="job-1",
        error=None,
        duration_ms=123,
        attempts=1,
    )


def _render_failure() -> RenderResult:
    return RenderResult(
        status="failed",
        image_path=None,
        backend="comfyui",
        prompt_id="job-1",
        error="renderer offline after acceptance",
        duration_ms=123,
        attempts=1,
    )


class FakeDirector:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def generate(self, scene: ObservableSceneState) -> RawVST:
        self.calls.append("director")
        assert scene.scene_id == SceneId("session:12")
        return _raw()


class FakeCanonicalizer:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def canonicalize(
        self,
        *,
        scene: ObservableSceneState,
        raw_vst: RawVST,
        worldpack: LoadedWorldpack,
    ) -> CanonicalVST:
        self.calls.append("canonicalizer")
        assert scene.scene_id == raw_vst.scene_id
        assert worldpack is not None
        return _canonical()


class FakeCompiler:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def compile(self, canonical_vst: CanonicalVST, config: object) -> RenderPromptContract:
        self.calls.append("compiler")
        assert canonical_vst.scene_id == SceneId("session:12")
        assert config is not None
        return _prompt_contract()


class FakeWorkflowBuilder:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def build(self, **kwargs: object) -> ComfyWorkflowRequest:
        self.calls.append("workflow")
        assert kwargs["contract"] == _prompt_contract()
        return _workflow_request()


class FakeRenderer:
    def __init__(self, calls: list[str], result: RenderResult) -> None:
        self.calls = calls
        self.result = result
        self.requests: list[ComfyWorkflowRequest] = []

    async def health_check(self) -> object:
        raise AssertionError("bridge must not add an extra health-check layer per turn")

    async def render(self, request: ComfyWorkflowRequest) -> RenderResult:
        self.calls.append("renderer")
        self.requests.append(request)
        return self.result


class FakeDiagnosticsStore:
    def __init__(
        self,
        calls: list[str],
        *,
        fail_on_save: int | None = None,
        error_factory: Callable[[], Exception] | None = None,
    ) -> None:
        self.calls = calls
        self.fail_on_save = fail_on_save
        self.error_factory = error_factory
        self.snapshots: list[object] = []

    async def save(self, snapshot: object) -> str:
        from epos.application.visual.bridge import VisualDiagnosticsPersistenceError

        self.calls.append("diagnostics")
        self.snapshots.append(snapshot)
        if self.fail_on_save == len(self.snapshots):
            if self.error_factory is not None:
                raise self.error_factory()
            raise VisualDiagnosticsPersistenceError("diagnostic disk unavailable")
        return "diagnostics/session_12.visual.json"


def _resources():
    from epos.application.visual.bridge import VisualPipelineResources

    return VisualPipelineResources(
        worldpack=_worldpack(),
        prompt_profile=PromptCompilerProfile(),
        workflow_profile=ComfyWorkflowProfile.model_construct(workflow_file="workflow.json"),
        workflow_template=ComfyWorkflowTemplate(
            prompt={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
            source="workflow.json",
        ),
        workflow_parameters=ComfyWorkflowBuildParameters(
            client_id="epos-session-12",
            seed=123456789,
        ),
    )


def _pipeline(calls: list[str], renderer_result: RenderResult, diagnostics: FakeDiagnosticsStore):
    from epos.application.visual.bridge import VisualTurnPipeline

    return VisualTurnPipeline(
        director=FakeDirector(calls),
        canonicalizer=FakeCanonicalizer(calls),
        compiler=FakeCompiler(calls),
        workflow_builder=FakeWorkflowBuilder(calls),
        renderer=FakeRenderer(calls, renderer_result),
        diagnostics=diagnostics,
    )


@pytest.mark.asyncio
async def test_bridge_enforces_required_visual_pipeline_order() -> None:
    calls: list[str] = []
    diagnostics = FakeDiagnosticsStore(calls)
    pipeline = _pipeline(calls, _render_success(), diagnostics)

    result = await pipeline.run(scene=_scene(), resources=_resources())

    assert calls == [
        "director",
        "canonicalizer",
        "compiler",
        "workflow",
        "diagnostics",
        "renderer",
        "diagnostics",
    ]
    assert result.render_result.status == "success"
    assert result.render_result.prompt_id == "job-1"
    assert result.diagnostics_path == "diagnostics/session_12.visual.json"
    assert result.diagnostics_error is None


@pytest.mark.asyncio
async def test_pre_render_diagnostics_persist_full_python_contract_before_renderer() -> None:
    calls: list[str] = []
    diagnostics = FakeDiagnosticsStore(calls)
    pipeline = _pipeline(calls, _render_success(), diagnostics)

    result = await pipeline.run(scene=_scene(), resources=_resources())

    assert len(diagnostics.snapshots) == 2
    prepared = diagnostics.snapshots[0]
    assert prepared.phase == "prepared"
    assert prepared.raw_vst.scene_id == SceneId("session:12")
    assert prepared.canonical_vst.scene_id == SceneId("session:12")
    assert prepared.prompt_contract.positive_prompt == "canonical positive"
    assert prepared.prompt_contract.negative_prompt == "fixed negative"
    assert prepared.workflow_request == _workflow_request()
    assert prepared.render_result is None
    assert result.workflow_request == _workflow_request()


@pytest.mark.asyncio
async def test_renderer_failure_is_persisted_and_returned_without_new_llm_call() -> None:
    calls: list[str] = []
    diagnostics = FakeDiagnosticsStore(calls)
    pipeline = _pipeline(calls, _render_failure(), diagnostics)

    result = await pipeline.run(scene=_scene(), resources=_resources())

    assert calls.count("director") == 1
    assert calls.count("renderer") == 1
    assert result.render_result.status == "failed"
    assert result.render_result.prompt_id == "job-1"
    final = diagnostics.snapshots[-1]
    assert final.phase == "rendered"
    assert final.render_result == _render_failure()


@pytest.mark.asyncio
async def test_pre_render_diagnostics_failure_prevents_comfy_submission() -> None:
    from epos.application.visual.bridge import VisualDiagnosticsPersistenceError

    calls: list[str] = []
    diagnostics = FakeDiagnosticsStore(calls, fail_on_save=1)
    pipeline = _pipeline(calls, _render_success(), diagnostics)

    with pytest.raises(VisualDiagnosticsPersistenceError, match="diagnostic disk unavailable"):
        await pipeline.run(scene=_scene(), resources=_resources())

    assert "renderer" not in calls


@pytest.mark.asyncio
async def test_final_diagnostics_failure_does_not_trigger_duplicate_render() -> None:
    calls: list[str] = []
    diagnostics = FakeDiagnosticsStore(calls, fail_on_save=2)
    pipeline = _pipeline(calls, _render_success(), diagnostics)

    result = await pipeline.run(scene=_scene(), resources=_resources())

    assert calls.count("renderer") == 1
    assert calls.count("director") == 1
    assert result.render_result.status == "success"
    assert result.render_result.prompt_id == "job-1"
    assert result.diagnostics_error == "diagnostic disk unavailable"


def test_bridge_contract_does_not_expose_raw_prompt_or_direct_comfy_llm_path() -> None:
    from epos.application.visual.bridge import VisualPipelineResources, VisualPipelineResult

    resource_fields = set(VisualPipelineResources.model_fields)
    result_fields = set(VisualPipelineResult.model_fields)

    assert "llm_prompt" not in resource_fields
    assert "stable_diffusion_prompt" not in resource_fields
    assert "raw_player_input" not in resource_fields
    assert "world_state" not in resource_fields
    assert "raw_vst" in result_fields
    assert "canonical_vst" in result_fields
    assert "prompt_contract" in result_fields
    assert "workflow_request" in result_fields
    assert "render_result" in result_fields

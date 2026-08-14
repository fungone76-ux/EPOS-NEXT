"""Coordinate the complete Visual Director -> ComfyUI pipeline for one scene."""

from __future__ import annotations

from epos.application.visual.bridge.errors import VisualDiagnosticsPersistenceError
from epos.application.visual.bridge.models import (
    VisualPipelineDiagnostics,
    VisualPipelineResources,
    VisualPipelineResult,
)
from epos.application.visual.bridge.ports import (
    PromptCompilerPort,
    VisualCanonicalizerPort,
    VisualDiagnosticsStorePort,
    VisualDirectorPort,
)
from epos.application.visual.models import ObservableSceneState
from epos.application.visual.prompt import WorldpackVisualConfig
from epos.application.visual.rendering import RendererPort
from epos.application.visual.workflow import (
    ComfyWorkflowBuilderPort,
    ComfyWorkflowRequest,
)


class VisualTurnPipeline:
    """Thin application coordinator; every visual subsystem remains replaceable."""

    def __init__(
        self,
        *,
        director: VisualDirectorPort,
        canonicalizer: VisualCanonicalizerPort,
        compiler: PromptCompilerPort,
        workflow_builder: ComfyWorkflowBuilderPort,
        renderer: RendererPort[ComfyWorkflowRequest],
        diagnostics: VisualDiagnosticsStorePort,
    ) -> None:
        self._director = director
        self._canonicalizer = canonicalizer
        self._compiler = compiler
        self._workflow_builder = workflow_builder
        self._renderer = renderer
        self._diagnostics = diagnostics

    async def run(
        self,
        *,
        scene: ObservableSceneState,
        resources: VisualPipelineResources,
    ) -> VisualPipelineResult:
        raw_vst = await self._director.generate(scene)
        canonical_vst = self._canonicalizer.canonicalize(
            scene=scene,
            raw_vst=raw_vst,
            worldpack=resources.worldpack,
        )
        visual_config = WorldpackVisualConfig.from_loaded_worldpack(
            resources.worldpack,
            profile=resources.prompt_profile,
        )
        prompt_contract = self._compiler.compile(canonical_vst, visual_config)
        workflow_request = self._workflow_builder.build(
            contract=prompt_contract,
            template=resources.workflow_template,
            profile=resources.workflow_profile,
            parameters=resources.workflow_parameters,
        )

        prepared = VisualPipelineDiagnostics(
            phase="prepared",
            scene_id=scene.scene_id,
            raw_vst=raw_vst,
            canonical_vst=canonical_vst,
            prompt_contract=prompt_contract,
            workflow_request=workflow_request,
            render_result=None,
        )
        diagnostics_path = await self._diagnostics.save(prepared)

        render_result = await self._renderer.render(workflow_request)
        rendered = prepared.model_copy(
            update={"phase": "rendered", "render_result": render_result}
        )

        diagnostics_error: str | None = None
        try:
            diagnostics_path = await self._diagnostics.save(rendered)
        except VisualDiagnosticsPersistenceError as exc:
            diagnostics_error = str(exc)

        return VisualPipelineResult(
            raw_vst=raw_vst,
            canonical_vst=canonical_vst,
            prompt_contract=prompt_contract,
            workflow_request=workflow_request,
            render_result=render_result,
            diagnostics_path=diagnostics_path,
            diagnostics_error=diagnostics_error,
        )

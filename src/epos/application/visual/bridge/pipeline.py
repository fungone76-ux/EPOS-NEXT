"""Coordinate the complete renderer-neutral visual pipeline for one scene."""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from epos.application.visual.bridge.errors import VisualDiagnosticsPersistenceError
from epos.application.visual.bridge.models import (
    VisualPipelineDiagnostics,
    VisualPipelineResources,
    VisualPipelineResult,
)
from epos.application.visual.bridge.ports import (
    PromptCompilerPort,
    RenderRequestBuilderPort,
    VisualCanonicalizerPort,
    VisualDiagnosticsStorePort,
    VisualDirectorPort,
)
from epos.application.visual.models import ObservableSceneState
from epos.application.visual.prompt import WorldpackVisualConfig
from epos.application.visual.rendering import RendererPort

if TYPE_CHECKING:
    from epos.application.visual.recovery.models import PendingRender
    from epos.application.visual.recovery.ports import PendingRenderStorePort

RequestT = TypeVar("RequestT")


class VisualTurnPipeline(Generic[RequestT]):
    """Thin coordinator; renderer-specific work begins after prompt compilation."""

    def __init__(
        self,
        *,
        director: VisualDirectorPort,
        canonicalizer: VisualCanonicalizerPort,
        compiler: PromptCompilerPort,
        render_request_builder: RenderRequestBuilderPort[RequestT],
        renderer: RendererPort[RequestT],
        diagnostics: VisualDiagnosticsStorePort,
        pending_renders: PendingRenderStorePort | None = None,
    ) -> None:
        self._director = director
        self._canonicalizer = canonicalizer
        self._compiler = compiler
        self._render_request_builder = render_request_builder
        self._renderer = renderer
        self._diagnostics = diagnostics
        self._pending_renders = pending_renders

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
        built_request = self._render_request_builder.build(
            prompt_contract,
            seed=resources.seed,
        )

        prepared = VisualPipelineDiagnostics(
            phase="prepared",
            scene_id=scene.scene_id,
            raw_vst=raw_vst,
            canonical_vst=canonical_vst,
            prompt_contract=prompt_contract,
            render_request=built_request.snapshot,
            render_result=None,
        )
        diagnostics_path = await self._diagnostics.save(prepared)

        pending: PendingRender | None = None
        if self._pending_renders is not None:
            from epos.application.visual.recovery.models import PendingRender

            pending = PendingRender(
                session_id=scene.session_id,
                turn_number=scene.time.turn_number,
                scene_id=scene.scene_id,
                canonical_vst=canonical_vst,
                prompt_contract=prompt_contract,
                render_request=built_request.snapshot,
            )
            await self._pending_renders.save(pending)

        render_result = await self._renderer.render(built_request.request)
        rendered = prepared.model_copy(
            update={"phase": "rendered", "render_result": render_result}
        )

        diagnostics_error: str | None = None
        try:
            diagnostics_path = await self._diagnostics.save(rendered)
        except VisualDiagnosticsPersistenceError as exc:
            diagnostics_error = str(exc)

        if (
            render_result.status == "success"
            and self._pending_renders is not None
            and pending is not None
        ):
            await self._pending_renders.delete(pending.session_id, pending.turn_number)

        return VisualPipelineResult(
            raw_vst=raw_vst,
            canonical_vst=canonical_vst,
            prompt_contract=prompt_contract,
            render_request=built_request.snapshot,
            render_result=render_result,
            diagnostics_path=diagnostics_path,
            diagnostics_error=diagnostics_error,
        )

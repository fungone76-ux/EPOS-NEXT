from __future__ import annotations

import pytest

from epos.application.turn import VisualTurnPipelineAdapter
from epos.application.visual.bridge import VisualPipelineResources, VisualPipelineResult
from epos.application.visual.models import ObservableSceneState
from epos.domain.ids import SceneId


class RecordingVisualPipeline:
    def __init__(self, result: VisualPipelineResult) -> None:
        self.result = result
        self.scene = None
        self.resources = None

    async def run(self, *, scene, resources):
        self.scene = scene
        self.resources = resources
        return self.result


class FixedVisualResources:
    def __init__(self, resources: VisualPipelineResources) -> None:
        self.resources = resources
        self.scene = None

    def resources_for(self, scene: ObservableSceneState) -> VisualPipelineResources:
        self.scene = scene
        return self.resources


@pytest.mark.asyncio
async def test_visual_turn_adapter_connects_scene_to_full_visual_pipeline() -> None:
    scene = ObservableSceneState.model_construct(scene_id=SceneId("session-1:2"))
    resources = VisualPipelineResources.model_construct(seed=123456789)
    expected = VisualPipelineResult.model_construct()
    pipeline = RecordingVisualPipeline(expected)
    provider = FixedVisualResources(resources)
    adapter = VisualTurnPipelineAdapter(pipeline=pipeline, resources=provider)

    result = await adapter.render(scene)

    assert result is expected
    assert provider.scene is scene
    assert pipeline.scene is scene
    assert pipeline.resources is resources

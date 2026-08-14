from __future__ import annotations

from pathlib import Path

import pytest

from epos.application.visual.prompt import RenderPromptContract
from epos.application.visual.workflow import (
    ComfyWorkflowBuildParameters,
    ComfyWorkflowProfile,
    WorkflowValidationError,
)
from epos.domain.world_state import RenderingConfig
from epos.infrastructure.rendering.comfy import (
    ComfyWorkflowBuilder,
    FileSystemComfyWorkflowTemplateLoader,
)
from epos.infrastructure.worldpacks.loader import FileSystemWorldpackLoader


@pytest.mark.asyncio
async def test_resort_worldpack_declares_and_builds_its_canonical_comfy_workflow() -> None:
    root = Path("worldpacks/resort_world")
    loaded = await FileSystemWorldpackLoader().load(root, session_id="workflow-profile")

    profile = ComfyWorkflowProfile.from_rendering_config(
        loaded.world_state.rendering_config
    )

    assert profile.workflow_file == "workflows/comfy_workflow_image.json"
    assert profile.nodes.positive_prompt.node_id == "2"
    assert profile.nodes.negative_prompt.node_id == "3"
    assert profile.nodes.checkpoint.node_id == "1"
    assert tuple(slot.node_id for slot in profile.lora_slots) == ("20", "23")

    template = await FileSystemComfyWorkflowTemplateLoader().load(
        root / profile.workflow_file
    )
    contract = RenderPromptContract(
        positive_prompt="resort canonical positive",
        negative_prompt="resort fixed negative",
        loras=(),
        checkpoint=None,
        width=896,
        height=1152,
        sampler=None,
        scheduler=None,
        steps=None,
        cfg=None,
    )

    first = ComfyWorkflowBuilder().build(
        contract=contract,
        template=template,
        profile=profile,
        parameters=ComfyWorkflowBuildParameters(
            client_id="resort-session",
            seed=424242,
        ),
    )
    second = ComfyWorkflowBuilder().build(
        contract=contract,
        template=template,
        profile=profile,
        parameters=ComfyWorkflowBuildParameters(
            client_id="resort-session",
            seed=424242,
        ),
    )

    assert first.model_dump_json() == second.model_dump_json()
    assert "20" not in first.prompt
    assert "23" not in first.prompt


def test_missing_comfy_profile_fails_readably() -> None:
    with pytest.raises(WorkflowValidationError, match="ComfyUI profile"):
        ComfyWorkflowProfile.from_rendering_config(RenderingConfig())

from __future__ import annotations

from pathlib import Path

import pytest

from epos.application.visual.canonical import ResolvedLora
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

ROOT = Path("worldpacks/resort_world")


async def _profile_and_template():
    loaded = await FileSystemWorldpackLoader().load(ROOT, session_id="workflow-profile")
    profile = ComfyWorkflowProfile.from_rendering_config(
        loaded.world_state.rendering_config
    )
    template = await FileSystemComfyWorkflowTemplateLoader().load(
        ROOT / profile.workflow_file
    )
    return profile, template


def _contract(*, loras: tuple[ResolvedLora, ...] = ()) -> RenderPromptContract:
    return RenderPromptContract(
        positive_prompt="resort canonical positive",
        negative_prompt="resort fixed negative",
        loras=loras,
        checkpoint=None,
        width=896,
        height=1152,
        sampler=None,
        scheduler=None,
        steps=None,
        cfg=None,
    )


def _parameters() -> ComfyWorkflowBuildParameters:
    return ComfyWorkflowBuildParameters(
        client_id="resort-session",
        seed=424242,
    )


@pytest.mark.asyncio
async def test_resort_worldpack_declares_and_builds_its_canonical_comfy_workflow() -> None:
    profile, template = await _profile_and_template()

    assert profile.workflow_file == "workflows/comfy_workflow_image.json"
    assert profile.nodes.positive_prompt.node_id == "2"
    assert profile.nodes.negative_prompt.node_id == "3"
    assert profile.nodes.checkpoint.node_id == "1"
    assert tuple(slot.node_id for slot in profile.lora_slots) == ("20", "23")

    contract = _contract()
    first = ComfyWorkflowBuilder().build(
        contract=contract,
        template=template,
        profile=profile,
        parameters=_parameters(),
    )
    second = ComfyWorkflowBuilder().build(
        contract=contract,
        template=template,
        profile=profile,
        parameters=_parameters(),
    )

    assert first.model_dump_json() == second.model_dump_json()
    assert "20" not in first.prompt
    assert "23" not in first.prompt


def test_missing_comfy_profile_fails_readably() -> None:
    with pytest.raises(WorkflowValidationError, match="ComfyUI profile"):
        ComfyWorkflowProfile.from_rendering_config(RenderingConfig())


@pytest.mark.asyncio
async def test_duplicate_requested_lora_aliases_fail_before_building_graph() -> None:
    profile, template = await _profile_and_template()
    contract = _contract(
        loras=(
            ResolvedLora(
                entity_id="victoria",
                alias="victoria_main",
                filename="victoria_main.safetensors",
            ),
            ResolvedLora(
                entity_id="other",
                alias="victoria_main",
                filename="other.safetensors",
            ),
        )
    )

    with pytest.raises(WorkflowValidationError, match="duplicate LoRA alias"):
        ComfyWorkflowBuilder().build(
            contract=contract,
            template=template,
            profile=profile,
            parameters=_parameters(),
        )


@pytest.mark.asyncio
async def test_unsupported_reference_to_lora_output_fails_instead_of_dangling() -> None:
    profile, template = await _profile_and_template()
    template.prompt["10"] = {
        "inputs": {"unexpected": ["23", 2]},
        "class_type": "Passthrough",
        "_meta": {"title": "Unsupported LoRA output consumer"},
    }
    contract = _contract(
        loras=(
            ResolvedLora(
                entity_id="victoria",
                alias="victoria_main",
                filename="victoria_main.safetensors",
            ),
        )
    )

    with pytest.raises(WorkflowValidationError, match="unsupported LoRA output"):
        ComfyWorkflowBuilder().build(
            contract=contract,
            template=template,
            profile=profile,
            parameters=_parameters(),
        )

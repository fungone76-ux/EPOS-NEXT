from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from epos.application.visual.canonical import ResolvedLora
from epos.application.visual.prompt import RenderPromptContract
from epos.application.visual.workflow import (
    ComfyInputBinding,
    ComfyLoraSlot,
    ComfyLoraStrengthRule,
    ComfyWorkflowBuildParameters,
    ComfyWorkflowNodeBindings,
    ComfyWorkflowProfile,
    ComfyWorkflowTemplate,
    WorkflowValidationError,
)
from epos.infrastructure.rendering.comfy import (
    ComfyWorkflowBuilder,
    FileSystemComfyWorkflowTemplateLoader,
)

FIXTURE = Path("tests/fixtures/comfy_workflow_image.json")


def _binding(node_id: str, class_type: str, input_name: str) -> ComfyInputBinding:
    return ComfyInputBinding(
        node_id=node_id,
        expected_class_type=class_type,
        input_name=input_name,
    )


def _profile() -> ComfyWorkflowProfile:
    return ComfyWorkflowProfile(
        workflow_file="workflows/comfy_workflow_image.json",
        base_model_node_id="1",
        base_model_expected_class_type="CheckpointLoaderSimple",
        nodes=ComfyWorkflowNodeBindings(
            positive_prompt=_binding("2", "CLIPTextEncode", "text"),
            negative_prompt=_binding("3", "CLIPTextEncode", "text"),
            checkpoint=_binding("1", "CheckpointLoaderSimple", "ckpt_name"),
            seed=_binding("4", "SamplerCustom", "noise_seed"),
            cfg=_binding("4", "SamplerCustom", "cfg"),
            sampler=_binding("5", "KSamplerSelect", "sampler_name"),
            scheduler=_binding("6", "BasicScheduler", "scheduler"),
            steps=_binding("6", "BasicScheduler", "steps"),
            width=_binding("7", "EmptyLatentImage", "width"),
            height=_binding("7", "EmptyLatentImage", "height"),
        ),
        lora_slots=(
            ComfyLoraSlot(node_id="20", expected_class_type="LoraLoader"),
            ComfyLoraSlot(node_id="23", expected_class_type="LoraLoader"),
        ),
        default_lora_strength_model=0.8,
        default_lora_strength_clip=1.0,
        lora_strengths=(
            ComfyLoraStrengthRule(
                alias="victoria_main",
                strength_model=0.7,
                strength_clip=0.75,
            ),
        ),
        dimension_multiple=8,
        min_dimension=64,
        max_dimension=2048,
    )


def _template() -> ComfyWorkflowTemplate:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return ComfyWorkflowTemplate(prompt=raw, source=str(FIXTURE))


def _contract(*, loras: tuple[ResolvedLora, ...] | None = None) -> RenderPromptContract:
    return RenderPromptContract(
        positive_prompt="canonical positive prompt",
        negative_prompt="fixed canonical negative prompt",
        loras=(
            ResolvedLora(
                entity_id="victoria",
                alias="victoria_main",
                filename="victoria_main.safetensors",
            ),
        )
        if loras is None
        else loras,
        checkpoint="resort_model.safetensors",
        width=832,
        height=1216,
        sampler="euler",
        scheduler="karras",
        steps=32,
        cfg=6.5,
    )


def _build(
    *,
    contract: RenderPromptContract | None = None,
    template: ComfyWorkflowTemplate | None = None,
    profile: ComfyWorkflowProfile | None = None,
):
    return ComfyWorkflowBuilder().build(
        contract=_contract() if contract is None else contract,
        template=_template() if template is None else template,
        profile=_profile() if profile is None else profile,
        parameters=ComfyWorkflowBuildParameters(
            client_id="epos-session-12",
            seed=987654321,
        ),
    )


def _inputs(prompt: dict[str, object], node_id: str) -> dict[str, object]:
    node = prompt[node_id]
    assert isinstance(node, dict)
    inputs = node["inputs"]
    assert isinstance(inputs, dict)
    return inputs


def test_builder_injects_authorized_runtime_fields() -> None:
    request = _build()
    prompt = request.prompt

    assert request.client_id == "epos-session-12"
    assert _inputs(prompt, "2")["text"] == "canonical positive prompt"
    assert _inputs(prompt, "3")["text"] == "fixed canonical negative prompt"
    assert _inputs(prompt, "1")["ckpt_name"] == "resort_model.safetensors"
    assert _inputs(prompt, "4")["noise_seed"] == 987654321
    assert _inputs(prompt, "4")["cfg"] == 6.5
    assert _inputs(prompt, "5")["sampler_name"] == "euler"
    assert _inputs(prompt, "6")["scheduler"] == "karras"
    assert _inputs(prompt, "6")["steps"] == 32
    assert _inputs(prompt, "7")["width"] == 832
    assert _inputs(prompt, "7")["height"] == 1216


def test_builder_does_not_mutate_template_or_unrelated_nodes() -> None:
    template = _template()
    before = deepcopy(template)
    node_8 = deepcopy(template.prompt["8"])
    node_9 = deepcopy(template.prompt["9"])

    request = _build(template=template)

    assert template == before
    assert request.prompt["8"] == node_8
    assert request.prompt["9"] == node_9


def test_single_requested_lora_removes_unused_slot_and_rewires_consumers() -> None:
    request = _build()
    prompt = request.prompt

    assert "20" in prompt
    assert "23" not in prompt
    assert _inputs(prompt, "20")["lora_name"] == "victoria_main.safetensors"
    assert _inputs(prompt, "20")["strength_model"] == 0.7
    assert _inputs(prompt, "20")["strength_clip"] == 0.75
    assert _inputs(prompt, "20")["model"] == ["1", 0]
    assert _inputs(prompt, "20")["clip"] == ["1", 1]
    assert _inputs(prompt, "2")["clip"] == ["20", 1]
    assert _inputs(prompt, "3")["clip"] == ["20", 1]
    assert _inputs(prompt, "4")["model"] == ["20", 0]
    assert _inputs(prompt, "6")["model"] == ["20", 0]


def test_no_requested_loras_removes_all_slots_and_reconnects_checkpoint() -> None:
    request = _build(contract=_contract(loras=()))
    prompt = request.prompt

    assert "20" not in prompt
    assert "23" not in prompt
    assert _inputs(prompt, "2")["clip"] == ["1", 1]
    assert _inputs(prompt, "3")["clip"] == ["1", 1]
    assert _inputs(prompt, "4")["model"] == ["1", 0]
    assert _inputs(prompt, "6")["model"] == ["1", 0]
    serialized = json.dumps(prompt, sort_keys=True)
    assert "<lora_name>" not in serialized
    assert "detail_slider_v4.safetensors" not in serialized


def test_two_requested_loras_build_ordered_chain() -> None:
    contract = _contract(
        loras=(
            ResolvedLora(
                entity_id="victoria",
                alias="victoria_main",
                filename="victoria_main.safetensors",
            ),
            ResolvedLora(
                entity_id="player",
                alias="player_style",
                filename="player_style.safetensors",
            ),
        )
    )

    request = _build(contract=contract)
    prompt = request.prompt

    assert _inputs(prompt, "20")["lora_name"] == "victoria_main.safetensors"
    assert _inputs(prompt, "23")["lora_name"] == "player_style.safetensors"
    assert _inputs(prompt, "23")["strength_model"] == 0.8
    assert _inputs(prompt, "23")["strength_clip"] == 1.0
    assert _inputs(prompt, "23")["model"] == ["20", 0]
    assert _inputs(prompt, "23")["clip"] == ["20", 1]
    assert _inputs(prompt, "2")["clip"] == ["23", 1]
    assert _inputs(prompt, "4")["model"] == ["23", 0]


def test_more_loras_than_configured_slots_fails_readably() -> None:
    loras = tuple(
        ResolvedLora(
            entity_id=f"npc-{index}",
            alias=f"alias-{index}",
            filename=f"lora-{index}.safetensors",
        )
        for index in range(3)
    )

    with pytest.raises(WorkflowValidationError, match="LoRA slots"):
        _build(contract=_contract(loras=loras))


def test_wrong_node_type_fails_before_mutation() -> None:
    template = _template()
    node = template.prompt["2"]
    assert isinstance(node, dict)
    node["class_type"] = "WrongNode"

    with pytest.raises(WorkflowValidationError, match="class_type"):
        _build(template=template)


def test_missing_authorized_input_fails_readably() -> None:
    template = _template()
    node = template.prompt["4"]
    assert isinstance(node, dict)
    inputs = node["inputs"]
    assert isinstance(inputs, dict)
    del inputs["cfg"]

    with pytest.raises(WorkflowValidationError, match="cfg"):
        _build(template=template)


def test_dimension_policy_is_profile_driven_and_fails_closed() -> None:
    contract = _contract().model_copy(update={"width": 834})

    with pytest.raises(WorkflowValidationError, match="dimension"):
        _build(contract=contract)


def test_empty_checkpoint_is_rejected() -> None:
    contract = _contract().model_copy(update={"checkpoint": ""})

    with pytest.raises(WorkflowValidationError, match="checkpoint"):
        _build(contract=contract)


def test_optional_render_settings_preserve_valid_template_values() -> None:
    contract = _contract().model_copy(
        update={
            "checkpoint": None,
            "sampler": None,
            "scheduler": None,
            "steps": None,
            "cfg": None,
        }
    )

    request = _build(contract=contract)
    prompt = request.prompt

    assert _inputs(prompt, "1")["ckpt_name"] == "luna_main_model.safetensors"
    assert _inputs(prompt, "4")["cfg"] == 7
    assert _inputs(prompt, "5")["sampler_name"] == "dpmpp_2m"
    assert _inputs(prompt, "6")["scheduler"] == "normal"
    assert _inputs(prompt, "6")["steps"] == 24
    assert _inputs(prompt, "4")["noise_seed"] == 987654321


def test_profile_rejects_duplicate_lora_slot_ids() -> None:
    profile = _profile()

    with pytest.raises(ValidationError, match="duplicate LoRA slot"):
        profile.model_copy(
            update={
                "lora_slots": (
                    ComfyLoraSlot(node_id="20", expected_class_type="LoraLoader"),
                    ComfyLoraSlot(node_id="20", expected_class_type="LoraLoader"),
                )
            }
        ).model_validate(profile.model_dump())


@pytest.mark.asyncio
async def test_template_loader_reads_api_json_without_blocking_contract(tmp_path: Path) -> None:
    target = tmp_path / "workflow.json"
    target.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    loaded = await FileSystemComfyWorkflowTemplateLoader().load(target)

    assert loaded.source == str(target)
    assert loaded.prompt["1"] == _template().prompt["1"]


@pytest.mark.asyncio
async def test_template_loader_reports_invalid_json(tmp_path: Path) -> None:
    target = tmp_path / "workflow.json"
    target.write_text("{not-json", encoding="utf-8")

    with pytest.raises(WorkflowValidationError, match="workflow template"):
        await FileSystemComfyWorkflowTemplateLoader().load(target)

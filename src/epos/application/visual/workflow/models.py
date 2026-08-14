"""Strict application contracts for configurable ComfyUI workflow building."""

from __future__ import annotations

from pydantic import Field, JsonValue, ValidationError, model_validator

from epos.application.visual.workflow.errors import WorkflowValidationError
from epos.domain.base import DomainModel
from epos.domain.world_state import RenderingConfig


class ComfyInputBinding(DomainModel):
    node_id: str = Field(min_length=1)
    expected_class_type: str = Field(min_length=1)
    input_name: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_non_blank(self) -> ComfyInputBinding:
        if not self.node_id.strip():
            raise ValueError("Comfy node_id must not be blank")
        if not self.expected_class_type.strip():
            raise ValueError("Comfy expected_class_type must not be blank")
        if not self.input_name.strip():
            raise ValueError("Comfy input_name must not be blank")
        return self


class ComfyWorkflowNodeBindings(DomainModel):
    positive_prompt: ComfyInputBinding
    negative_prompt: ComfyInputBinding
    checkpoint: ComfyInputBinding
    seed: ComfyInputBinding
    cfg: ComfyInputBinding
    sampler: ComfyInputBinding
    scheduler: ComfyInputBinding
    steps: ComfyInputBinding
    width: ComfyInputBinding
    height: ComfyInputBinding


class ComfyLoraSlot(DomainModel):
    node_id: str = Field(min_length=1)
    expected_class_type: str = Field(default="LoraLoader", min_length=1)
    lora_name_input: str = Field(default="lora_name", min_length=1)
    strength_model_input: str = Field(default="strength_model", min_length=1)
    strength_clip_input: str = Field(default="strength_clip", min_length=1)
    model_input: str = Field(default="model", min_length=1)
    clip_input: str = Field(default="clip", min_length=1)
    model_output_index: int = Field(default=0, ge=0)
    clip_output_index: int = Field(default=1, ge=0)

    @model_validator(mode="after")
    def validate_non_blank(self) -> ComfyLoraSlot:
        values = (
            self.node_id,
            self.expected_class_type,
            self.lora_name_input,
            self.strength_model_input,
            self.strength_clip_input,
            self.model_input,
            self.clip_input,
        )
        if any(not value.strip() for value in values):
            raise ValueError("Comfy LoRA slot fields must not be blank")
        if self.model_output_index == self.clip_output_index:
            raise ValueError("Comfy LoRA model/clip output indexes must differ")
        return self


class ComfyLoraStrengthRule(DomainModel):
    alias: str = Field(min_length=1)
    strength_model: float = Field(ge=-10.0, le=10.0)
    strength_clip: float = Field(ge=-10.0, le=10.0)

    @model_validator(mode="after")
    def validate_alias(self) -> ComfyLoraStrengthRule:
        if not self.alias.strip():
            raise ValueError("Comfy LoRA strength alias must not be blank")
        return self


class ComfyWorkflowProfile(DomainModel):
    """Worldpack/model-specific node mapping; the engine never assumes node IDs."""

    workflow_file: str = Field(min_length=1)
    base_model_node_id: str = Field(min_length=1)
    base_model_expected_class_type: str = Field(min_length=1)
    base_model_output_index: int = Field(default=0, ge=0)
    base_clip_output_index: int = Field(default=1, ge=0)
    nodes: ComfyWorkflowNodeBindings
    lora_slots: tuple[ComfyLoraSlot, ...] = ()
    default_lora_strength_model: float = Field(default=0.8, ge=-10.0, le=10.0)
    default_lora_strength_clip: float = Field(default=1.0, ge=-10.0, le=10.0)
    lora_strengths: tuple[ComfyLoraStrengthRule, ...] = ()
    dimension_multiple: int = Field(default=8, ge=1)
    min_dimension: int = Field(default=64, ge=1)
    max_dimension: int = Field(default=4096, ge=1)

    @classmethod
    def from_rendering_config(cls, config: RenderingConfig) -> ComfyWorkflowProfile:
        """Build the typed Comfy profile declared by the active Worldpack."""
        raw = config.settings.get("comfyui")
        if not isinstance(raw, dict):
            raise WorkflowValidationError(
                "Worldpack ComfyUI profile is missing from rendering_config.comfyui"
            )
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            raise WorkflowValidationError(
                f"Worldpack ComfyUI profile is invalid: {exc}"
            ) from exc

    @model_validator(mode="after")
    def validate_profile(self) -> ComfyWorkflowProfile:
        if not self.workflow_file.strip():
            raise ValueError("Comfy workflow_file must not be blank")
        if not self.base_model_node_id.strip():
            raise ValueError("Comfy base_model_node_id must not be blank")
        if not self.base_model_expected_class_type.strip():
            raise ValueError("Comfy base_model_expected_class_type must not be blank")
        if self.min_dimension > self.max_dimension:
            raise ValueError("Comfy min_dimension must not exceed max_dimension")

        slot_ids: set[str] = set()
        for slot in self.lora_slots:
            key = slot.node_id.strip()
            if key in slot_ids:
                raise ValueError(f"duplicate LoRA slot: {slot.node_id}")
            if key == self.base_model_node_id.strip():
                raise ValueError("LoRA slot cannot reuse the base model node")
            slot_ids.add(key)

        strength_aliases: set[str] = set()
        for rule in self.lora_strengths:
            key = rule.alias.strip().casefold()
            if key in strength_aliases:
                raise ValueError(f"duplicate LoRA strength alias: {rule.alias}")
            strength_aliases.add(key)
        return self

    def lora_strength_for(self, alias: str) -> tuple[float, float]:
        key = alias.strip().casefold()
        for rule in self.lora_strengths:
            if rule.alias.strip().casefold() == key:
                return rule.strength_model, rule.strength_clip
        return self.default_lora_strength_model, self.default_lora_strength_clip


class ComfyWorkflowBuildParameters(DomainModel):
    client_id: str = Field(min_length=1)
    seed: int = Field(ge=0, le=(2**64) - 1)

    @model_validator(mode="after")
    def validate_client_id(self) -> ComfyWorkflowBuildParameters:
        if not self.client_id.strip():
            raise ValueError("Comfy client_id must not be blank")
        return self


class ComfyWorkflowTemplate(DomainModel):
    prompt: dict[str, JsonValue]
    source: str | None = None

    @model_validator(mode="after")
    def validate_prompt(self) -> ComfyWorkflowTemplate:
        if not self.prompt:
            raise ValueError("Comfy workflow template must contain nodes")
        return self


class ComfyWorkflowRequest(DomainModel):
    prompt: dict[str, JsonValue]
    client_id: str = Field(min_length=1)

"""Deterministic ComfyUI API workflow construction for Module 14."""

from __future__ import annotations

from copy import deepcopy

from pydantic import JsonValue

from epos.application.visual.canonical import ResolvedLora
from epos.application.visual.prompt import RenderPromptContract
from epos.application.visual.workflow import (
    ComfyInputBinding,
    ComfyLoraSlot,
    ComfyWorkflowBuildParameters,
    ComfyWorkflowProfile,
    ComfyWorkflowRequest,
    ComfyWorkflowTemplate,
    WorkflowValidationError,
)

JsonObject = dict[str, JsonValue]


class ComfyWorkflowBuilder:
    """Inject only authorized runtime values into a validated API workflow copy."""

    def build(
        self,
        *,
        contract: RenderPromptContract,
        template: ComfyWorkflowTemplate,
        profile: ComfyWorkflowProfile,
        parameters: ComfyWorkflowBuildParameters,
    ) -> ComfyWorkflowRequest:
        self._validate_contract(contract, profile)
        prompt = deepcopy(template.prompt)
        self._validate_template(prompt, profile)

        self._set_binding(prompt, profile.nodes.positive_prompt, contract.positive_prompt)
        self._set_binding(prompt, profile.nodes.negative_prompt, contract.negative_prompt)
        self._apply_optional_string(
            prompt,
            profile.nodes.checkpoint,
            contract.checkpoint,
            label="checkpoint",
        )
        self._set_binding(prompt, profile.nodes.seed, parameters.seed)
        self._apply_optional_number(
            prompt,
            profile.nodes.cfg,
            contract.cfg,
            label="cfg",
        )
        self._apply_optional_string(
            prompt,
            profile.nodes.sampler,
            contract.sampler,
            label="sampler",
        )
        self._apply_optional_string(
            prompt,
            profile.nodes.scheduler,
            contract.scheduler,
            label="scheduler",
        )
        self._apply_optional_int(
            prompt,
            profile.nodes.steps,
            contract.steps,
            label="steps",
        )
        self._set_binding(prompt, profile.nodes.width, contract.width)
        self._set_binding(prompt, profile.nodes.height, contract.height)

        removed_slots = self._rebuild_lora_chain(prompt, contract.loras, profile)
        self._assert_no_dangling_lora_references(prompt, removed_slots)

        return ComfyWorkflowRequest(
            prompt=prompt,
            client_id=parameters.client_id,
        )

    def _validate_contract(
        self,
        contract: RenderPromptContract,
        profile: ComfyWorkflowProfile,
    ) -> None:
        if not contract.positive_prompt.strip():
            raise WorkflowValidationError("positive prompt must not be blank")
        if not contract.negative_prompt.strip():
            raise WorkflowValidationError("negative prompt must not be blank")
        if contract.checkpoint is not None and not contract.checkpoint.strip():
            raise WorkflowValidationError("checkpoint must not be blank")
        if contract.sampler is not None and not contract.sampler.strip():
            raise WorkflowValidationError("sampler must not be blank")
        if contract.scheduler is not None and not contract.scheduler.strip():
            raise WorkflowValidationError("scheduler must not be blank")
        if contract.steps is not None and contract.steps < 1:
            raise WorkflowValidationError("steps must be at least 1")
        if contract.cfg is not None and contract.cfg <= 0:
            raise WorkflowValidationError("cfg must be greater than 0")

        self._validate_dimension(contract.width, "width", profile)
        self._validate_dimension(contract.height, "height", profile)
        self._validate_lora_contract(contract.loras, profile)

    @staticmethod
    def _validate_dimension(
        value: int,
        label: str,
        profile: ComfyWorkflowProfile,
    ) -> None:
        if value < profile.min_dimension or value > profile.max_dimension:
            raise WorkflowValidationError(
                f"invalid {label} dimension {value}; expected "
                f"{profile.min_dimension}..{profile.max_dimension}"
            )
        if value % profile.dimension_multiple != 0:
            raise WorkflowValidationError(
                f"invalid {label} dimension {value}; must be a multiple of "
                f"{profile.dimension_multiple}"
            )

    @staticmethod
    def _validate_lora_contract(
        loras: tuple[ResolvedLora, ...],
        profile: ComfyWorkflowProfile,
    ) -> None:
        if len(loras) > len(profile.lora_slots):
            raise WorkflowValidationError(
                f"requested {len(loras)} LoRA(s) but profile exposes only "
                f"{len(profile.lora_slots)} LoRA slots"
            )
        aliases: set[str] = set()
        for lora in loras:
            alias = lora.alias.strip()
            filename = lora.filename.strip()
            if not alias:
                raise WorkflowValidationError("LoRA alias must not be blank")
            if not filename:
                raise WorkflowValidationError(f"LoRA filename missing for alias {alias}")
            key = alias.casefold()
            if key in aliases:
                raise WorkflowValidationError(f"duplicate LoRA alias in render contract: {alias}")
            aliases.add(key)

    def _validate_template(
        self,
        prompt: JsonObject,
        profile: ComfyWorkflowProfile,
    ) -> None:
        self._validate_all_node_shapes(prompt)
        self._require_node_class(
            prompt,
            profile.base_model_node_id,
            profile.base_model_expected_class_type,
        )
        bindings = (
            profile.nodes.positive_prompt,
            profile.nodes.negative_prompt,
            profile.nodes.checkpoint,
            profile.nodes.seed,
            profile.nodes.cfg,
            profile.nodes.sampler,
            profile.nodes.scheduler,
            profile.nodes.steps,
            profile.nodes.width,
            profile.nodes.height,
        )
        for binding in bindings:
            self._binding_inputs(prompt, binding)
        for slot in profile.lora_slots:
            self._lora_inputs(prompt, slot)

        self._require_string_input(prompt, profile.nodes.positive_prompt, "positive prompt")
        self._require_string_input(prompt, profile.nodes.negative_prompt, "negative prompt")
        self._require_string_input(prompt, profile.nodes.checkpoint, "checkpoint")
        self._require_int_input(prompt, profile.nodes.seed, "seed", minimum=0)
        self._require_number_input(prompt, profile.nodes.cfg, "cfg", greater_than=0.0)
        self._require_string_input(prompt, profile.nodes.sampler, "sampler")
        self._require_string_input(prompt, profile.nodes.scheduler, "scheduler")
        self._require_int_input(prompt, profile.nodes.steps, "steps", minimum=1)
        self._require_int_input(prompt, profile.nodes.width, "width", minimum=1)
        self._require_int_input(prompt, profile.nodes.height, "height", minimum=1)

    def _validate_all_node_shapes(self, prompt: JsonObject) -> None:
        for node_id, value in prompt.items():
            if not isinstance(value, dict):
                raise WorkflowValidationError(f"workflow node {node_id} must be an object")
            class_type = value.get("class_type")
            if not isinstance(class_type, str) or not class_type.strip():
                raise WorkflowValidationError(
                    f"workflow node {node_id} has invalid class_type"
                )
            inputs = value.get("inputs")
            if not isinstance(inputs, dict):
                raise WorkflowValidationError(f"workflow node {node_id} has invalid inputs")

    def _require_node_class(
        self,
        prompt: JsonObject,
        node_id: str,
        expected_class_type: str,
    ) -> JsonObject:
        node = self._node(prompt, node_id)
        actual = node.get("class_type")
        if actual != expected_class_type:
            raise WorkflowValidationError(
                f"workflow node {node_id} class_type mismatch: expected "
                f"{expected_class_type}, got {actual}"
            )
        return node

    def _binding_inputs(
        self,
        prompt: JsonObject,
        binding: ComfyInputBinding,
    ) -> JsonObject:
        node = self._require_node_class(
            prompt,
            binding.node_id,
            binding.expected_class_type,
        )
        inputs = self._inputs(node, binding.node_id)
        if binding.input_name not in inputs:
            raise WorkflowValidationError(
                f"workflow node {binding.node_id} missing input {binding.input_name}"
            )
        return inputs

    def _lora_inputs(
        self,
        prompt: JsonObject,
        slot: ComfyLoraSlot,
    ) -> JsonObject:
        node = self._require_node_class(
            prompt,
            slot.node_id,
            slot.expected_class_type,
        )
        inputs = self._inputs(node, slot.node_id)
        required = (
            slot.lora_name_input,
            slot.strength_model_input,
            slot.strength_clip_input,
            slot.model_input,
            slot.clip_input,
        )
        for input_name in required:
            if input_name not in inputs:
                raise WorkflowValidationError(
                    f"workflow LoRA node {slot.node_id} missing input {input_name}"
                )
        return inputs

    def _set_binding(
        self,
        prompt: JsonObject,
        binding: ComfyInputBinding,
        value: JsonValue,
    ) -> None:
        inputs = self._binding_inputs(prompt, binding)
        inputs[binding.input_name] = value

    def _apply_optional_string(
        self,
        prompt: JsonObject,
        binding: ComfyInputBinding,
        value: str | None,
        *,
        label: str,
    ) -> None:
        if value is None:
            self._require_string_input(prompt, binding, label)
            return
        if not value.strip():
            raise WorkflowValidationError(f"{label} must not be blank")
        self._set_binding(prompt, binding, value)

    def _apply_optional_int(
        self,
        prompt: JsonObject,
        binding: ComfyInputBinding,
        value: int | None,
        *,
        label: str,
    ) -> None:
        if value is None:
            self._require_int_input(prompt, binding, label, minimum=1)
            return
        if isinstance(value, bool) or value < 1:
            raise WorkflowValidationError(f"{label} must be a positive integer")
        self._set_binding(prompt, binding, value)

    def _apply_optional_number(
        self,
        prompt: JsonObject,
        binding: ComfyInputBinding,
        value: float | None,
        *,
        label: str,
    ) -> None:
        if value is None:
            self._require_number_input(prompt, binding, label, greater_than=0.0)
            return
        if value <= 0:
            raise WorkflowValidationError(f"{label} must be greater than 0")
        self._set_binding(prompt, binding, value)

    def _require_string_input(
        self,
        prompt: JsonObject,
        binding: ComfyInputBinding,
        label: str,
    ) -> str:
        value = self._binding_inputs(prompt, binding)[binding.input_name]
        if not isinstance(value, str) or not value.strip():
            raise WorkflowValidationError(
                f"workflow {label} input {binding.node_id}.{binding.input_name} "
                "must be a non-blank string"
            )
        return value

    def _require_int_input(
        self,
        prompt: JsonObject,
        binding: ComfyInputBinding,
        label: str,
        *,
        minimum: int,
    ) -> int:
        value = self._binding_inputs(prompt, binding)[binding.input_name]
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise WorkflowValidationError(
                f"workflow {label} input {binding.node_id}.{binding.input_name} "
                f"must be an integer >= {minimum}"
            )
        return value

    def _require_number_input(
        self,
        prompt: JsonObject,
        binding: ComfyInputBinding,
        label: str,
        *,
        greater_than: float,
    ) -> float:
        value = self._binding_inputs(prompt, binding)[binding.input_name]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value <= greater_than
        ):
            raise WorkflowValidationError(
                f"workflow {label} input {binding.node_id}.{binding.input_name} "
                f"must be numeric > {greater_than}"
            )
        return float(value)

    def _rebuild_lora_chain(
        self,
        prompt: JsonObject,
        loras: tuple[ResolvedLora, ...],
        profile: ComfyWorkflowProfile,
    ) -> set[str]:
        all_slots = profile.lora_slots
        active_slots = all_slots[: len(loras)]
        inactive_slots = all_slots[len(loras) :]
        all_slot_ids = {slot.node_id for slot in all_slots}
        active_ids = {slot.node_id for slot in active_slots}
        slot_by_id = {slot.node_id: slot for slot in all_slots}

        previous_node_id = profile.base_model_node_id
        previous_model_output = profile.base_model_output_index
        previous_clip_output = profile.base_clip_output_index

        for lora, slot in zip(loras, active_slots, strict=True):
            inputs = self._lora_inputs(prompt, slot)
            strength_model, strength_clip = profile.lora_strength_for(lora.alias)
            inputs[slot.lora_name_input] = lora.filename
            inputs[slot.strength_model_input] = strength_model
            inputs[slot.strength_clip_input] = strength_clip
            inputs[slot.model_input] = self._connection(
                previous_node_id,
                previous_model_output,
            )
            inputs[slot.clip_input] = self._connection(
                previous_node_id,
                previous_clip_output,
            )
            previous_node_id = slot.node_id
            previous_model_output = slot.model_output_index
            previous_clip_output = slot.clip_output_index

        final_model = self._connection(previous_node_id, previous_model_output)
        final_clip = self._connection(previous_node_id, previous_clip_output)

        for slot in inactive_slots:
            del prompt[slot.node_id]

        for node_id, node_value in prompt.items():
            if node_id in active_ids:
                continue
            if not isinstance(node_value, dict):
                continue
            inputs_value = node_value.get("inputs")
            if not isinstance(inputs_value, dict):
                continue
            for input_name, value in tuple(inputs_value.items()):
                reference = self._connection_reference(value)
                if reference is None:
                    continue
                referenced_node, output_index = reference
                if referenced_node not in all_slot_ids:
                    continue
                slot = slot_by_id[referenced_node]
                if output_index == slot.model_output_index:
                    inputs_value[input_name] = deepcopy(final_model)
                elif output_index == slot.clip_output_index:
                    inputs_value[input_name] = deepcopy(final_clip)
                else:
                    raise WorkflowValidationError(
                        f"workflow references unsupported LoRA output "
                        f"{referenced_node}:{output_index}"
                    )

        return {slot.node_id for slot in inactive_slots}

    def _assert_no_dangling_lora_references(
        self,
        prompt: JsonObject,
        removed_slots: set[str],
    ) -> None:
        if not removed_slots:
            return
        for node_id, node_value in prompt.items():
            if not isinstance(node_value, dict):
                continue
            inputs_value = node_value.get("inputs")
            if not isinstance(inputs_value, dict):
                continue
            for input_name, value in inputs_value.items():
                reference = self._connection_reference(value)
                if reference is not None and reference[0] in removed_slots:
                    raise WorkflowValidationError(
                        f"workflow node {node_id}.{input_name} still references "
                        f"removed LoRA node {reference[0]}"
                    )

    @staticmethod
    def _connection(node_id: str, output_index: int) -> list[JsonValue]:
        return [node_id, output_index]

    @staticmethod
    def _connection_reference(value: JsonValue) -> tuple[str, int] | None:
        if not isinstance(value, list) or len(value) != 2:
            return None
        node_id = value[0]
        output_index = value[1]
        if not isinstance(node_id, str):
            return None
        if isinstance(output_index, bool) or not isinstance(output_index, int):
            return None
        return node_id, output_index

    @staticmethod
    def _node(prompt: JsonObject, node_id: str) -> JsonObject:
        value = prompt.get(node_id)
        if not isinstance(value, dict):
            raise WorkflowValidationError(f"required workflow node missing: {node_id}")
        return value

    @staticmethod
    def _inputs(node: JsonObject, node_id: str) -> JsonObject:
        value = node.get("inputs")
        if not isinstance(value, dict):
            raise WorkflowValidationError(f"workflow node {node_id} has invalid inputs")
        return value

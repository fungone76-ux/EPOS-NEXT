from __future__ import annotations

from epos.application.visual.prompt import RenderPromptContract
from epos.application.visual.workflow import (
    ComfyWorkflowBuildParameters,
    ComfyWorkflowProfile,
    ComfyWorkflowRequest,
    ComfyWorkflowTemplate,
)
from epos.infrastructure.rendering.comfy import ComfyRenderRequestBuilder


class FakeWorkflowBuilder:
    def build(
        self,
        *,
        contract: RenderPromptContract,
        template: ComfyWorkflowTemplate,
        profile: ComfyWorkflowProfile,
        parameters: ComfyWorkflowBuildParameters,
    ) -> ComfyWorkflowRequest:
        assert contract.positive_prompt == "canonical"
        assert template.source == "workflow.json"
        assert profile.workflow_file == "workflow.json"
        assert parameters.seed == 42
        assert parameters.client_id == "client-1"
        return ComfyWorkflowRequest(
            prompt={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
            client_id=parameters.client_id,
        )


def test_comfy_request_builder_satisfies_renderer_neutral_boundary() -> None:
    builder = ComfyRenderRequestBuilder(
        workflow_builder=FakeWorkflowBuilder(),
        template=ComfyWorkflowTemplate(
            prompt={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
            source="workflow.json",
        ),
        profile=ComfyWorkflowProfile.model_construct(workflow_file="workflow.json"),
        client_id="client-1",
    )
    contract = RenderPromptContract(
        positive_prompt="canonical",
        negative_prompt="fixed negative",
        width=896,
        height=1152,
    )

    built = builder.build(contract, seed=42)

    assert built.request.client_id == "client-1"
    assert built.snapshot.backend == "comfyui"
    assert built.snapshot.request_id.startswith("comfyui-")
    assert built.snapshot.payload["client_id"] == "client-1"
    repeated = builder.build(contract, seed=42)
    assert repeated.snapshot.request_id == built.snapshot.request_id

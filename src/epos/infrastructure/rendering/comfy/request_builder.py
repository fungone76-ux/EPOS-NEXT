"""Adapter that exposes the existing Comfy workflow builder through the generic render-request port."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from epos.application.visual.bridge import BuiltRenderRequest, RenderRequestSnapshot
from epos.application.visual.prompt import RenderPromptContract
from epos.application.visual.workflow import (
    ComfyWorkflowBuildParameters,
    ComfyWorkflowBuilderPort,
    ComfyWorkflowProfile,
    ComfyWorkflowRequest,
    ComfyWorkflowTemplate,
)


class ComfyRenderRequestBuilder:
    """Bind static Comfy resources while keeping the application bridge backend-neutral."""

    def __init__(
        self,
        *,
        workflow_builder: ComfyWorkflowBuilderPort,
        template: ComfyWorkflowTemplate,
        profile: ComfyWorkflowProfile,
        client_id: str,
    ) -> None:
        self._workflow_builder = workflow_builder
        self._template = template.model_copy(deep=True)
        self._profile = profile.model_copy(deep=True)
        self._client_id = client_id

    def build(
        self,
        contract: RenderPromptContract,
        *,
        seed: int,
    ) -> BuiltRenderRequest[ComfyWorkflowRequest]:
        request = self._workflow_builder.build(
            contract=contract,
            template=self._template,
            profile=self._profile,
            parameters=ComfyWorkflowBuildParameters(
                client_id=self._client_id,
                seed=seed,
            ),
        )
        payload = {
            "prompt": deepcopy(request.prompt),
            "client_id": request.client_id,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        request_id = f"comfyui-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]}"
        return BuiltRenderRequest(
            request=request,
            snapshot=RenderRequestSnapshot(
                backend="comfyui",
                request_id=request_id,
                payload=payload,
            ),
        )

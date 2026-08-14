"""Application ports for Module 14 workflow construction."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from epos.application.visual.prompt import RenderPromptContract
from epos.application.visual.workflow.models import (
    ComfyWorkflowBuildParameters,
    ComfyWorkflowProfile,
    ComfyWorkflowRequest,
    ComfyWorkflowTemplate,
)


class ComfyWorkflowBuilderPort(Protocol):
    def build(
        self,
        *,
        contract: RenderPromptContract,
        template: ComfyWorkflowTemplate,
        profile: ComfyWorkflowProfile,
        parameters: ComfyWorkflowBuildParameters,
    ) -> ComfyWorkflowRequest: ...


class ComfyWorkflowTemplateLoaderPort(Protocol):
    async def load(self, path: Path) -> ComfyWorkflowTemplate: ...

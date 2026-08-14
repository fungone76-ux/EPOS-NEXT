"""Typed contracts for the Module 16 visual bridge."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from epos.application.visual.canonical import CanonicalVST
from epos.application.visual.prompt import PromptCompilerProfile, RenderPromptContract
from epos.application.visual.rendering import RenderResult
from epos.application.visual.vst import RawVST
from epos.application.visual.workflow import (
    ComfyWorkflowBuildParameters,
    ComfyWorkflowProfile,
    ComfyWorkflowRequest,
    ComfyWorkflowTemplate,
)
from epos.application.worldpacks.models import LoadedWorldpack
from epos.domain.base import DomainModel
from epos.domain.ids import SceneId


class VisualPipelineResources(DomainModel):
    """Already-resolved resources required to render one observable scene."""

    worldpack: LoadedWorldpack
    prompt_profile: PromptCompilerProfile
    workflow_profile: ComfyWorkflowProfile
    workflow_template: ComfyWorkflowTemplate
    workflow_parameters: ComfyWorkflowBuildParameters


class VisualPipelineDiagnostics(DomainModel):
    """Persistable snapshot sufficient to diagnose or later rerender the scene."""

    phase: Literal["prepared", "rendered"]
    scene_id: SceneId
    raw_vst: RawVST
    canonical_vst: CanonicalVST
    prompt_contract: RenderPromptContract
    workflow_request: ComfyWorkflowRequest
    render_result: RenderResult | None = None

    @model_validator(mode="after")
    def validate_scene_binding(self) -> VisualPipelineDiagnostics:
        if self.raw_vst.scene_id != self.scene_id:
            raise ValueError("raw VST scene_id does not match diagnostics scene_id")
        if self.canonical_vst.scene_id != self.scene_id:
            raise ValueError("canonical VST scene_id does not match diagnostics scene_id")
        if self.phase == "prepared" and self.render_result is not None:
            raise ValueError("prepared visual diagnostics must not contain render_result")
        if self.phase == "rendered" and self.render_result is None:
            raise ValueError("rendered visual diagnostics require render_result")
        return self


class VisualPipelineResult(DomainModel):
    """Complete visual result returned to the future turn orchestrator."""

    raw_vst: RawVST
    canonical_vst: CanonicalVST
    prompt_contract: RenderPromptContract
    workflow_request: ComfyWorkflowRequest
    render_result: RenderResult
    diagnostics_path: str
    diagnostics_error: str | None = None

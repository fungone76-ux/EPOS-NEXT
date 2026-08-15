"""Typed contracts for the renderer-neutral visual bridge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from pydantic import Field, JsonValue, model_validator

from epos.application.visual.canonical import CanonicalVST
from epos.application.visual.prompt import PromptCompilerProfile, RenderPromptContract
from epos.application.visual.rendering import RenderResult
from epos.application.visual.vst import RawVST
from epos.application.worldpacks.models import LoadedWorldpack
from epos.domain.base import DomainModel
from epos.domain.ids import SceneId

RequestT = TypeVar("RequestT")


class RenderRequestSnapshot(DomainModel):
    """Backend-neutral, JSON-safe request snapshot persisted before rendering."""

    backend: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    payload: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class BuiltRenderRequest(Generic[RequestT]):
    """Typed backend request paired with its persistable diagnostic snapshot."""

    request: RequestT
    snapshot: RenderRequestSnapshot


class VisualPipelineResources(DomainModel):
    """Renderer-neutral resources required to process one observable scene."""

    worldpack: LoadedWorldpack
    prompt_profile: PromptCompilerProfile
    seed: int = Field(ge=0, le=2**64 - 1)


class VisualPipelineDiagnostics(DomainModel):
    """Persistable snapshot sufficient to diagnose or later rerender the scene."""

    phase: Literal["prepared", "rendered"]
    scene_id: SceneId
    raw_vst: RawVST
    canonical_vst: CanonicalVST
    prompt_contract: RenderPromptContract
    render_request: RenderRequestSnapshot
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
    """Complete renderer-neutral visual result returned to turn orchestration."""

    raw_vst: RawVST
    canonical_vst: CanonicalVST
    prompt_contract: RenderPromptContract
    render_request: RenderRequestSnapshot
    render_result: RenderResult
    diagnostics_path: str
    diagnostics_error: str | None = None

"""Persistent render-recovery contracts."""

from __future__ import annotations

from pydantic import model_validator

from epos.application.visual.bridge.models import RenderRequestSnapshot
from epos.application.visual.canonical import CanonicalVST
from epos.application.visual.prompt import RenderPromptContract
from epos.application.visual.rendering import RenderResult
from epos.domain.base import DomainModel
from epos.domain.ids import SceneId, SessionId, TurnNumber


class PendingRender(DomainModel):
    """Everything required to retry an image without replaying the turn or any LLM."""

    session_id: SessionId
    turn_number: TurnNumber
    scene_id: SceneId
    canonical_vst: CanonicalVST
    prompt_contract: RenderPromptContract
    render_request: RenderRequestSnapshot
    request_version: str = "1"

    @model_validator(mode="after")
    def validate_scene_binding(self) -> PendingRender:
        if self.canonical_vst.scene_id != self.scene_id:
            raise ValueError("pending render canonical VST belongs to another scene")
        if int(self.turn_number) != int(self.canonical_vst.time.turn_number):
            raise ValueError("pending render turn does not match canonical VST")
        return self


class RetryImageResult(DomainModel):
    pending: PendingRender
    render_result: RenderResult

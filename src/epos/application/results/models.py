"""Stable player/API-facing turn result contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, SceneId, SessionId, SkillId, TurnNumber


class TurnDialogueLine(DomainModel):
    speaker_id: EntityId
    text: str = Field(min_length=1)


class TurnCheckResult(DomainModel):
    skill_id: SkillId
    difficulty: int = Field(ge=1, le=6)
    dice: tuple[int, ...]
    success_count: int = Field(ge=0)
    outcome: Literal[
        "critical_failure",
        "failure",
        "partial_success",
        "full_success",
    ]


class TurnGameResult(DomainModel):
    outcome: Literal[
        "no_check",
        "declined",
        "critical_failure",
        "failure",
        "partial_success",
        "full_success",
    ]
    check: TurnCheckResult | None = None


class TurnVisualLora(DomainModel):
    entity_id: EntityId
    alias: str
    filename: str


class TurnVisualResult(DomainModel):
    vst_status: Literal["ok", "failed", "unavailable"]
    positive_prompt: str | None = None
    negative_prompt: str | None = None
    loras: tuple[TurnVisualLora, ...] = ()
    image_path: str | None = None
    render_status: Literal["success", "failed", "not_attempted"]
    render_error: str | None = None
    backend: str | None = None
    prompt_id: str | None = None
    diagnostics_path: str | None = None
    retry_available: bool = False


class TurnIssue(DomainModel):
    phase: str
    code: str
    message: str


class TurnDiagnostics(DomainModel):
    scene_id: SceneId
    checkpoint_reused: bool = False
    memory_stored: bool = False
    issues: tuple[TurnIssue, ...] = ()


class TurnResult(DomainModel):
    """Stable boundary returned to GUI/API without authoritative WorldState."""

    session_id: SessionId
    turn_number: TurnNumber
    narration: str
    dialogues: tuple[TurnDialogueLine, ...] = ()
    game: TurnGameResult
    visual: TurnVisualResult
    diagnostics: TurnDiagnostics

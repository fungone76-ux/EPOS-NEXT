"""Strict semantic contracts emitted by the Visual Director LLM."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, LocationId, SceneId
from epos.domain.semantic import SEMANTIC_TOKEN_PATTERN, SemanticToken

_TOKEN = re.compile(SEMANTIC_TOKEN_PATTERN)
_FORBIDDEN_RENDER_MARKERS = (
    "<lora:",
    "positive prompt",
    "negative prompt",
    "checkpoint=",
    "checkpoint:",
    "sampler=",
    "sampler:",
    "seed=",
    "seed:",
    "cfg=",
    "cfg:",
    "score_",
    "masterpiece",
)


def _normalize_description(value: str) -> str:
    normalized = " ".join(value.strip().split())
    lowered = normalized.casefold()
    if any(marker in lowered for marker in _FORBIDDEN_RENDER_MARKERS):
        raise ValueError("semantic intent must not contain prompt or render syntax")
    return normalized


def _normalize_tags(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        tag = value.strip().casefold()
        if not _TOKEN.fullmatch(tag):
            raise ValueError("semantic tags must be stable lowercase tokens")
        if tag not in normalized:
            normalized.append(tag)
    return tuple(normalized)


class SemanticIntent(DomainModel):
    """Short human-readable semantic intent, never Stable Diffusion syntax."""

    description: str = Field(min_length=1, max_length=180)
    tags: tuple[SemanticToken, ...] = ()

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _normalize_description(value)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _normalize_tags(values)


class VSTSubjectProminence(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    BACKGROUND = "background"


class SafetySignal(StrEnum):
    GENERAL = "general"
    ADULT_CONTEXT = "adult_context"
    INTIMATE_CONTEXT = "intimate_context"
    VIOLENCE_CONTEXT = "violence_context"


class VSTLocationIntent(DomainModel):
    location_id: LocationId
    environment: SemanticIntent | None = None


class VSTSubjectIntent(DomainModel):
    """Non-authoritative visual direction for one proposed subject."""

    entity_id: EntityId
    prominence: VSTSubjectProminence
    pose: SemanticIntent | None = None
    action: SemanticIntent | None = None
    body_orientation: SemanticIntent | None = None
    outfit_intent: SemanticIntent | None = None


class VSTActionIntent(DomainModel):
    participants: tuple[EntityId, ...] = ()
    intent: SemanticIntent
    shared: bool = False

    @model_validator(mode="after")
    def validate_participants(self) -> VSTActionIntent:
        if len(self.participants) != len(set(self.participants)):
            raise ValueError("action participant ids must be unique")
        return self


class VSTVisualFocus(DomainModel):
    subject_ids: tuple[EntityId, ...] = Field(min_length=1)
    intent: SemanticIntent

    @model_validator(mode="after")
    def validate_subject_ids(self) -> VSTVisualFocus:
        if len(self.subject_ids) != len(set(self.subject_ids)):
            raise ValueError("visual focus subject ids must be unique")
        return self


class VSTCameraIntent(DomainModel):
    shot: SemanticIntent
    angle: SemanticIntent | None = None
    composition: SemanticIntent | None = None


class VSTLightingIntent(DomainModel):
    intent: SemanticIntent


class VSTStyleIntent(DomainModel):
    intent: SemanticIntent


class VSTSafetyIntent(DomainModel):
    """Semantic classification only; never authority over body coverage or consent."""

    signal: SafetySignal = SafetySignal.GENERAL


class RawVST(DomainModel):
    """Raw Visual Semantic Table produced by the Visual Director LLM."""

    scene_id: SceneId
    location: VSTLocationIntent
    subjects: tuple[VSTSubjectIntent, ...] = Field(min_length=1)
    action: VSTActionIntent
    visual_focus: VSTVisualFocus
    camera: VSTCameraIntent
    lighting: VSTLightingIntent
    style: VSTStyleIntent
    safety: VSTSafetyIntent

    @model_validator(mode="after")
    def validate_unique_subjects(self) -> RawVST:
        subject_ids = tuple(subject.entity_id for subject in self.subjects)
        if len(subject_ids) != len(set(subject_ids)):
            raise ValueError("VST subject ids must be unique")
        return self

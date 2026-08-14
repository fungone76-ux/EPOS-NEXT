"""Strict Python-authoritative visual contracts produced by Module 12."""

from __future__ import annotations

from pydantic import model_validator

from epos.application.visual.models import SceneTime, SubjectKind
from epos.application.visual.vst import (
    SemanticIntent,
    VSTLightingIntent,
    VSTSafetyIntent,
    VSTStyleIntent,
    VSTSubjectProminence,
)
from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, LocationId, SceneId, WorldpackId
from epos.domain.outfit import OutfitState
from epos.domain.visual_state import VisualState


class ResolvedSemanticEntry(DomainModel):
    entry_id: str
    description: str = ""
    tags: tuple[str, ...] = ()
    positive_fragment: str = ""


class CanonicalVisualIdentity(DomainModel):
    base_prompt: str
    role_prompt: str = ""
    visual_gender: str
    canonical_traits: tuple[str, ...] = ()


class ResolvedLora(DomainModel):
    entity_id: EntityId
    alias: str
    filename: str


class CanonicalLocation(DomainModel):
    location_id: LocationId
    name: str
    environment: SemanticIntent | None = None


class CanonicalSubject(DomainModel):
    entity_id: EntityId
    kind: SubjectKind
    name: str
    role: str
    prominence: VSTSubjectProminence
    identity: CanonicalVisualIdentity
    outfit: OutfitState
    visual_state: VisualState
    position: str | None = None
    pose: ResolvedSemanticEntry | None = None
    action: ResolvedSemanticEntry | None = None
    body_orientation: ResolvedSemanticEntry | None = None
    lora: ResolvedLora | None = None


class CanonicalAction(DomainModel):
    participants: tuple[EntityId, ...] = ()
    semantic: ResolvedSemanticEntry
    shared: bool = False


class CanonicalVisualFocus(DomainModel):
    subject_ids: tuple[EntityId, ...]
    intent: SemanticIntent


class CanonicalCamera(DomainModel):
    semantic: ResolvedSemanticEntry


class CanonicalVST(DomainModel):
    scene_id: SceneId
    worldpack_id: WorldpackId
    time: SceneTime
    location: CanonicalLocation
    subjects: tuple[CanonicalSubject, ...]
    action: CanonicalAction
    visual_focus: CanonicalVisualFocus
    camera: CanonicalCamera
    lighting: VSTLightingIntent
    style: VSTStyleIntent
    safety: VSTSafetyIntent

    @model_validator(mode="after")
    def validate_reference_integrity(self) -> CanonicalVST:
        subject_ids = tuple(subject.entity_id for subject in self.subjects)
        if len(subject_ids) != len(set(subject_ids)):
            raise ValueError("canonical subject ids must be unique")
        rendered_ids = set(subject_ids)
        for participant in self.action.participants:
            if participant not in rendered_ids:
                raise ValueError(
                    f"canonical action participant is not rendered: {participant}"
                )
        for subject_id in self.visual_focus.subject_ids:
            if subject_id not in rendered_ids:
                raise ValueError(f"canonical focus subject is not rendered: {subject_id}")
        return self

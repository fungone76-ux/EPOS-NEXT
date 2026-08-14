"""Strict observable-scene contracts shared by narration, VST, image, and memory."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import field_validator, model_validator

from epos.application.actions.models import ResolvedCheck, ValidatedAction
from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, LocationId, SceneId, SessionId, TurnNumber, WorldpackId
from epos.domain.outfit import OutfitState
from epos.domain.visual_state import VisualState

_TOKEN = re.compile(r"^[a-z0-9][a-z0-9_.:-]*$")
_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:%-]*$")


def _semantic_token(value: str, *, field_name: str) -> str:
    normalized = value.strip().casefold()
    if not _TOKEN.fullmatch(normalized):
        raise ValueError(f"{field_name} must be one semantic token")
    return normalized


def _non_empty(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


class SubjectKind(StrEnum):
    PLAYER = "player"
    NPC = "npc"


class SceneLocation(DomainModel):
    location_id: LocationId
    name: str


class SceneTime(DomainModel):
    turn_number: TurnNumber
    day: int
    world_phase: str

    @field_validator("world_phase")
    @classmethod
    def validate_world_phase(cls, value: str) -> str:
        return _non_empty(value, field_name="world_phase")


class SceneSubjectCue(DomainModel):
    """Python-owned fine scene cues not derivable from WorldState alone."""

    entity_id: EntityId
    position: str | None = None
    mood_expressions: tuple[str, ...] = ()

    @field_validator("position")
    @classmethod
    def validate_position(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _semantic_token(value, field_name="position")

    @field_validator("mood_expressions")
    @classmethod
    def validate_mood_expressions(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            _semantic_token(value, field_name="mood expression") for value in values
        )


class ObservableSubject(DomainModel):
    entity_id: EntityId
    kind: SubjectKind
    name: str
    role: str
    outfit: OutfitState
    visual_state: VisualState
    position: str | None = None
    mood_expressions: tuple[str, ...] = ()


class ObservableConsequence(DomainModel):
    consequence_id: str
    kind: str
    fact: str
    subject_ids: tuple[EntityId, ...] = ()

    @field_validator("consequence_id")
    @classmethod
    def validate_consequence_id(cls, value: str) -> str:
        normalized = value.strip()
        if not _STABLE_ID.fullmatch(normalized):
            raise ValueError("consequence_id must be a stable token")
        return normalized

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        return _semantic_token(value, field_name="consequence kind")

    @field_validator("fact")
    @classmethod
    def validate_fact(cls, value: str) -> str:
        return _non_empty(value, field_name="observable consequence fact")


class AuthorizedDialogueLine(DomainModel):
    speaker_id: EntityId
    target_ids: tuple[EntityId, ...] = ()
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _non_empty(value, field_name="dialogue text")


class ResolvedSceneAction(DomainModel):
    action: ValidatedAction
    resolved_check: ResolvedCheck | None = None

    @model_validator(mode="after")
    def validate_resolved_check(self) -> ResolvedSceneAction:
        if self.resolved_check is None:
            return self
        if self.action.check is None:
            raise ValueError(
                "resolved check exists but validated action has no check proposal"
            )
        if (
            self.resolved_check.skill_id != self.action.check.skill_id
            or self.resolved_check.difficulty != self.action.check.difficulty
        ):
            raise ValueError("resolved check does not match validated action check")
        if (
            self.action.skill_rating is not None
            and self.resolved_check.rating != self.action.skill_rating
        ):
            raise ValueError(
                "resolved check rating does not match validated action skill rating"
            )
        return self


class VisualFocusCandidate(DomainModel):
    subject_ids: tuple[EntityId, ...]
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        return _semantic_token(value, field_name="visual focus reason")


class SceneObservationInput(DomainModel):
    """Already-authorized turn facts used to enrich facts derivable from WorldState."""

    action: ValidatedAction
    resolved_check: ResolvedCheck | None = None
    subject_cues: tuple[SceneSubjectCue, ...] = ()
    observable_consequences: tuple[ObservableConsequence, ...] = ()

    @model_validator(mode="after")
    def validate_unique_entries(self) -> SceneObservationInput:
        cue_ids = [cue.entity_id for cue in self.subject_cues]
        if len(cue_ids) != len(set(cue_ids)):
            raise ValueError("subject_cues must contain each entity at most once")
        consequence_ids = [item.consequence_id for item in self.observable_consequences]
        if len(consequence_ids) != len(set(consequence_ids)):
            raise ValueError("observable consequence ids must be unique")
        return self


class ObservableSceneState(DomainModel):
    """Disclosure-safe canonical representation of the current observable moment."""

    scene_id: SceneId
    session_id: SessionId
    worldpack_id: WorldpackId
    location: SceneLocation
    time: SceneTime
    visible_subjects: tuple[ObservableSubject, ...]
    resolved_action: ResolvedSceneAction
    observable_consequences: tuple[ObservableConsequence, ...] = ()
    authorized_dialogue: tuple[AuthorizedDialogueLine, ...] = ()
    visual_focus_candidate: VisualFocusCandidate | None = None

    @model_validator(mode="after")
    def validate_scene_integrity(self) -> ObservableSceneState:
        subject_ids = tuple(subject.entity_id for subject in self.visible_subjects)
        if len(subject_ids) != len(set(subject_ids)):
            raise ValueError("visible subject ids must be unique")

        player_subjects = tuple(
            subject
            for subject in self.visible_subjects
            if subject.kind is SubjectKind.PLAYER
        )
        if len(player_subjects) != 1:
            raise ValueError("observable scene must contain exactly one visible player subject")

        visible_ids = set(subject_ids)
        visible_npc_ids = {
            subject.entity_id
            for subject in self.visible_subjects
            if subject.kind is SubjectKind.NPC
        }

        invalid_action_targets = tuple(
            target_id
            for target_id in self.resolved_action.action.target_ids
            if target_id not in visible_ids
        )
        if invalid_action_targets:
            raise ValueError(
                "resolved action target is not visible in observable scene: "
                f"{invalid_action_targets[0]}"
            )

        consequence_ids = tuple(
            consequence.consequence_id
            for consequence in self.observable_consequences
        )
        if len(consequence_ids) != len(set(consequence_ids)):
            raise ValueError("observable consequence ids must be unique")
        for consequence in self.observable_consequences:
            invalid_subjects = tuple(
                subject_id
                for subject_id in consequence.subject_ids
                if subject_id not in visible_ids
            )
            if invalid_subjects:
                raise ValueError(
                    "observable consequence references non-visible subject "
                    f"{invalid_subjects[0]}"
                )

        focus = self.visual_focus_candidate
        if focus is not None:
            invalid_focus_subjects = tuple(
                subject_id
                for subject_id in focus.subject_ids
                if subject_id not in visible_ids
            )
            if invalid_focus_subjects:
                raise ValueError(
                    "visual focus references non-visible subject "
                    f"{invalid_focus_subjects[0]}"
                )

        for line in self.authorized_dialogue:
            if line.speaker_id not in visible_npc_ids:
                raise ValueError(
                    "authorized dialogue speaker must be a visible NPC: "
                    f"{line.speaker_id}"
                )
            invalid_targets = tuple(
                target_id
                for target_id in line.target_ids
                if target_id not in visible_ids
            )
            if invalid_targets:
                raise ValueError(
                    "authorized dialogue target is not visible: "
                    f"{invalid_targets[0]}"
                )

        return self

"""Build the minimal disclosure-safe context used only by the Visual Director."""

from __future__ import annotations

from epos.application.actions.models import CheckOutcome
from epos.application.intimacy.models import ConsentScope
from epos.application.visual.models import (
    ObservableSceneState,
    SceneLocation,
    SceneTime,
    SubjectKind,
    VisualFocusCandidate,
)
from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, SceneId


class VisualDirectorSubjectContext(DomainModel):
    entity_id: EntityId
    kind: SubjectKind
    name: str
    role: str
    position: str | None = None


class VisualDirectorActionContext(DomainModel):
    intent: str
    target_ids: tuple[EntityId, ...] = ()
    resolved_outcome: CheckOutcome | None = None


class VisualDirectorConsequenceContext(DomainModel):
    kind: str
    fact: str
    subject_ids: tuple[EntityId, ...] = ()


class VisualDirectorDialogueCue(DomainModel):
    speaker_id: EntityId
    target_ids: tuple[EntityId, ...] = ()


class VisualDirectorIntimacyContext(DomainModel):
    """Only the already-authorized adult semantic needed by visual direction."""

    scope: ConsentScope
    participant_ids: tuple[EntityId, EntityId]
    visual_intent: str
    visual_tags: tuple[str, ...] = ()


class VisualDirectorContext(DomainModel):
    """Only data needed to choose visual semantics, never SD prompt material."""

    scene_id: SceneId
    location: SceneLocation
    time: SceneTime
    subjects: tuple[VisualDirectorSubjectContext, ...]
    action: VisualDirectorActionContext
    consequences: tuple[VisualDirectorConsequenceContext, ...] = ()
    focus_candidate: VisualFocusCandidate | None = None
    dialogue_cues: tuple[VisualDirectorDialogueCue, ...] = ()
    authorized_intimacy: VisualDirectorIntimacyContext | None = None


class VisualDirectorContextBuilder:
    """Strip authoritative/private details that the visual director does not need."""

    def build(self, scene: ObservableSceneState) -> VisualDirectorContext:
        resolved_check = scene.resolved_action.resolved_check
        return VisualDirectorContext(
            scene_id=scene.scene_id,
            location=scene.location.model_copy(deep=True),
            time=scene.time.model_copy(deep=True),
            subjects=tuple(
                VisualDirectorSubjectContext(
                    entity_id=subject.entity_id,
                    kind=subject.kind,
                    name=subject.name,
                    role=subject.role,
                    position=subject.position,
                )
                for subject in scene.visible_subjects
            ),
            action=VisualDirectorActionContext(
                intent=scene.resolved_action.action.intent,
                target_ids=scene.resolved_action.action.target_ids,
                resolved_outcome=(
                    None if resolved_check is None else resolved_check.outcome
                ),
            ),
            consequences=tuple(
                VisualDirectorConsequenceContext(
                    kind=consequence.kind,
                    fact=consequence.fact,
                    subject_ids=consequence.subject_ids,
                )
                for consequence in scene.observable_consequences
            ),
            focus_candidate=(
                None
                if scene.visual_focus_candidate is None
                else scene.visual_focus_candidate.model_copy(deep=True)
            ),
            dialogue_cues=tuple(
                VisualDirectorDialogueCue(
                    speaker_id=line.speaker_id,
                    target_ids=line.target_ids,
                )
                for line in scene.authorized_dialogue
            ),
            authorized_intimacy=(
                None
                if scene.authorized_intimacy_visual is None
                else VisualDirectorIntimacyContext(
                    scope=scene.authorized_intimacy_visual.authorization.scope,
                    participant_ids=(
                        scene.authorized_intimacy_visual.player_id,
                        scene.authorized_intimacy_visual.npc_id,
                    ),
                    visual_intent=scene.authorized_intimacy_visual.visual_intent,
                    visual_tags=scene.authorized_intimacy_visual.visual_tags,
                )
            ),
        )

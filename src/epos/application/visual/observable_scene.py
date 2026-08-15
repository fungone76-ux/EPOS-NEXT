"""Pure Python builder for the canonical disclosure-safe observable scene."""

from __future__ import annotations

from epos.application.visual.errors import ObservableSceneValidationError
from epos.application.visual.models import (
    AuthorizedDialogueLine,
    ObservableSceneState,
    ObservableSubject,
    ResolvedSceneAction,
    SceneLocation,
    SceneObservationInput,
    SceneSubjectCue,
    SceneTime,
    SubjectKind,
    VisualFocusCandidate,
)
from epos.domain.ids import EntityId, SceneId
from epos.domain.world_state import WorldState


class ObservableSceneBuilder:
    """Build one local scene without exposing private WorldState information."""

    def build(
        self,
        *,
        state: WorldState,
        observation: SceneObservationInput,
    ) -> ObservableSceneState:
        location = state.locations.get(state.player.location_id)
        if location is None:
            raise ObservableSceneValidationError(
                f"player location is not defined: {state.player.location_id}"
            )

        visible_npc_ids = tuple(
            sorted(
                (
                    npc_id
                    for npc_id, npc in state.npcs.items()
                    if npc.location_id == state.player.location_id
                ),
                key=str,
            )
        )
        visible_ids = {state.player.entity_id, *visible_npc_ids}
        cues = self._validate_cues(observation=observation, visible_ids=visible_ids)
        self._validate_consequences(observation=observation, visible_ids=visible_ids)
        self._validate_resolved_check(observation)

        subjects = [
            self._player_subject(
                state=state,
                cue=cues.get(state.player.entity_id),
            )
        ]
        for npc_id in visible_npc_ids:
            npc = state.npcs[npc_id]
            cue = cues.get(npc_id)
            subjects.append(
                ObservableSubject(
                    entity_id=npc_id,
                    kind=SubjectKind.NPC,
                    name=npc.identity.name,
                    role=npc.identity.role,
                    outfit=npc.outfit.model_copy(deep=True),
                    visual_state=npc.visual_state.model_copy(deep=True),
                    position=None if cue is None else cue.position,
                    mood_expressions=() if cue is None else cue.mood_expressions,
                )
            )

        explicit_observation = observation.action.observation
        focus: VisualFocusCandidate | None
        if explicit_observation is not None:
            focus = VisualFocusCandidate(
                subject_ids=(explicit_observation.subject_id,),
                reason="player_observation",
                region=explicit_observation.region,
            )
        else:
            focus_ids = tuple(
                target_id
                for target_id in observation.action.target_ids
                if target_id in visible_ids
            )
            focus = (
                VisualFocusCandidate(subject_ids=focus_ids, reason="action_target")
                if focus_ids
                else None
            )

        return ObservableSceneState(
            scene_id=SceneId(f"{state.session_id}:{int(state.turn_number)}"),
            session_id=state.session_id,
            worldpack_id=state.worldpack_id,
            location=SceneLocation(
                location_id=location.location_id,
                name=location.name,
            ),
            time=SceneTime(
                turn_number=state.turn_number,
                day=state.day,
                world_phase=state.world_phase,
            ),
            visible_subjects=tuple(subjects),
            resolved_action=ResolvedSceneAction(
                action=observation.action.model_copy(deep=True),
                resolved_check=(
                    None
                    if observation.resolved_check is None
                    else observation.resolved_check.model_copy(deep=True)
                ),
            ),
            observable_consequences=tuple(
                item.model_copy(deep=True) for item in observation.observable_consequences
            ),
            visual_focus_candidate=focus,
            authorized_intimacy_visual=(
                None
                if observation.authorized_intimacy_visual is None
                else observation.authorized_intimacy_visual.model_copy(deep=True)
            ),
        )

    def attach_authorized_dialogue(
        self,
        *,
        scene: ObservableSceneState,
        dialogue: tuple[AuthorizedDialogueLine, ...],
    ) -> ObservableSceneState:
        visible_ids = {subject.entity_id for subject in scene.visible_subjects}
        visible_npc_ids = {
            subject.entity_id
            for subject in scene.visible_subjects
            if subject.kind is SubjectKind.NPC
        }

        for line in dialogue:
            if line.speaker_id not in visible_npc_ids:
                raise ObservableSceneValidationError(
                    f"dialogue speaker is not a visible NPC: {line.speaker_id}"
                )
            invalid_targets = tuple(
                target_id for target_id in line.target_ids if target_id not in visible_ids
            )
            if invalid_targets:
                raise ObservableSceneValidationError(
                    "dialogue target is not visible in the canonical scene: "
                    f"{invalid_targets[0]}"
                )

        payload = scene.model_dump(mode="python")
        payload["authorized_dialogue"] = tuple(
            line.model_copy(deep=True) for line in dialogue
        )
        return ObservableSceneState.model_validate(payload)

    @staticmethod
    def _player_subject(
        *,
        state: WorldState,
        cue: SceneSubjectCue | None,
    ) -> ObservableSubject:
        return ObservableSubject(
            entity_id=state.player.entity_id,
            kind=SubjectKind.PLAYER,
            name=state.player.name,
            role="player",
            outfit=state.player.outfit.model_copy(deep=True),
            visual_state=state.player.visual_state.model_copy(deep=True),
            position=None if cue is None else cue.position,
            mood_expressions=() if cue is None else cue.mood_expressions,
        )

    @staticmethod
    def _validate_cues(
        *,
        observation: SceneObservationInput,
        visible_ids: set[EntityId],
    ) -> dict[EntityId, SceneSubjectCue]:
        cues: dict[EntityId, SceneSubjectCue] = {}
        for cue in observation.subject_cues:
            if cue.entity_id not in visible_ids:
                raise ObservableSceneValidationError(
                    f"subject cue references entity that is not visible: {cue.entity_id}"
                )
            cues[cue.entity_id] = cue
        return cues

    @staticmethod
    def _validate_consequences(
        *,
        observation: SceneObservationInput,
        visible_ids: set[EntityId],
    ) -> None:
        for consequence in observation.observable_consequences:
            for subject_id in consequence.subject_ids:
                if subject_id not in visible_ids:
                    raise ObservableSceneValidationError(
                        "observable consequence references entity that is not visible: "
                        f"{subject_id}"
                    )

    @staticmethod
    def _validate_resolved_check(observation: SceneObservationInput) -> None:
        resolved = observation.resolved_check
        if resolved is None:
            return
        proposal = observation.action.check
        if proposal is None:
            raise ObservableSceneValidationError(
                "resolved check exists but the validated action has no check proposal"
            )
        if resolved.skill_id != proposal.skill_id or resolved.difficulty != proposal.difficulty:
            raise ObservableSceneValidationError(
                "resolved check does not match the validated action check proposal"
            )
        if (
            observation.action.skill_rating is not None
            and resolved.rating != observation.action.skill_rating
        ):
            raise ObservableSceneValidationError(
                "resolved check rating does not match the validated action skill rating"
            )

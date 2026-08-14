from __future__ import annotations

import pytest
from pydantic import ValidationError

from epos.application.actions.models import (
    CheckOutcome,
    CheckProposal,
    ResolvedCheck,
    ValidatedAction,
)
from epos.application.visual import (
    AuthorizedDialogueLine,
    ObservableConsequence,
    ObservableSceneBuilder,
    ObservableSceneState,
    SceneObservationInput,
    VisualFocusCandidate,
)
from epos.domain.ids import EntityId, LocationId, SessionId, SkillId, WorldpackId
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.outfit import OutfitItem, OutfitState
from epos.domain.player import PlayerState
from epos.domain.visual_state import VisualState
from epos.domain.world_state import LocationState, WorldState


def _state() -> WorldState:
    lobby = LocationId("lobby")
    return WorldState(
        session_id=SessionId("scene-contract"),
        worldpack_id=WorldpackId("test-world"),
        turn_number=7,
        day=2,
        world_phase="morning",
        player=PlayerState(
            entity_id=EntityId("player"),
            name="Player",
            location_id=lobby,
            outfit=OutfitState(
                items=(
                    OutfitItem(
                        item_id="shirt",
                        name="shirt",
                        slot="body",
                        layer=0,
                        color="blue",
                    ),
                )
            ),
            visual_state=VisualState(traits={"stance": "neutral"}),
        ),
        npcs={
            EntityId("victoria"): NPCState(
                identity=NPCIdentity(
                    entity_id=EntityId("victoria"),
                    name="Victoria",
                    role="host",
                ),
                location_id=lobby,
            ),
        },
        locations={
            lobby: LocationState(location_id=lobby, name="Lobby"),
        },
    )


def _scene() -> ObservableSceneState:
    return ObservableSceneBuilder().build(
        state=_state(),
        observation=SceneObservationInput(
            action=ValidatedAction(
                intent="dialogue",
                target_ids=(EntityId("victoria"),),
            )
        ),
    )


def test_same_authoritative_input_produces_byte_identical_scene_json() -> None:
    state = _state()
    observation = SceneObservationInput(
        action=ValidatedAction(
            intent="dialogue",
            target_ids=(EntityId("victoria"),),
        )
    )

    first = ObservableSceneBuilder().build(state=state, observation=observation)
    second = ObservableSceneBuilder().build(state=state, observation=observation)

    assert first.model_dump_json() == second.model_dump_json()


def test_returned_scene_is_deeply_isolated_from_worldstate() -> None:
    state = _state()
    scene = ObservableSceneBuilder().build(
        state=state,
        observation=SceneObservationInput(
            action=ValidatedAction(intent="observe")
        ),
    )

    scene.visible_subjects[0].outfit.items[0].color = "red"
    scene.visible_subjects[0].visual_state.traits["stance"] = "crouched"

    assert state.player.outfit.items[0].color == "blue"
    assert state.player.visual_state.traits["stance"] == "neutral"


def test_deserialized_scene_rejects_duplicate_visible_subject_ids() -> None:
    scene = _scene()
    payload = scene.model_dump(mode="python")
    payload["visible_subjects"] = (
        scene.visible_subjects[0],
        scene.visible_subjects[0],
    )

    with pytest.raises(ValidationError, match="visible subject"):
        ObservableSceneState.model_validate(payload)


def test_deserialized_scene_rejects_non_visible_focus_and_consequence_subjects() -> None:
    scene = _scene()
    payload = scene.model_dump(mode="python")
    payload["visual_focus_candidate"] = VisualFocusCandidate(
        subject_ids=(EntityId("remote"),),
        reason="action_target",
    )

    with pytest.raises(ValidationError, match="focus"):
        ObservableSceneState.model_validate(payload)

    payload = scene.model_dump(mode="python")
    payload["observable_consequences"] = (
        ObservableConsequence(
            consequence_id="remote_fact",
            kind="gesture",
            fact="A remote subject moves.",
            subject_ids=(EntityId("remote"),),
        ),
    )

    with pytest.raises(ValidationError, match="consequence"):
        ObservableSceneState.model_validate(payload)


def test_deserialized_scene_rejects_non_visible_or_player_dialogue_speaker() -> None:
    scene = _scene()
    for speaker_id in (EntityId("remote"), EntityId("player")):
        payload = scene.model_dump(mode="python")
        payload["authorized_dialogue"] = (
            AuthorizedDialogueLine(
                speaker_id=speaker_id,
                target_ids=(EntityId("victoria"),),
                text="Invalid speaker.",
            ),
        )

        with pytest.raises(ValidationError, match="dialogue"):
            ObservableSceneState.model_validate(payload)


def test_resolved_scene_action_rejects_check_inconsistent_with_validated_action() -> None:
    scene = _scene()
    payload = scene.model_dump(mode="python")
    payload["resolved_action"] = {
        "action": ValidatedAction(
            intent="persuasion",
            target_ids=(EntityId("victoria"),),
            check=CheckProposal(
                skill_id=SkillId("negoziazione"),
                difficulty=4,
            ),
            skill_rating=2,
        ),
        "resolved_check": ResolvedCheck(
            skill_id=SkillId("negoziazione"),
            difficulty=5,
            rating=2,
            pool_size=2,
            dice=(6, 2),
            success_count=1,
            outcome=CheckOutcome.PARTIAL_SUCCESS,
        ),
    }

    with pytest.raises(ValidationError, match="resolved check"):
        ObservableSceneState.model_validate(payload)

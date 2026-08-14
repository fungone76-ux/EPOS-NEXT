from __future__ import annotations

from copy import deepcopy

import pytest

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
    ObservableSceneValidationError,
    SceneObservationInput,
    SceneSubjectCue,
    SubjectKind,
)
from epos.domain.ids import EntityId, LocationId, SessionId, SkillId, WorldpackId
from epos.domain.knowledge import KnowledgeState
from epos.domain.npc import NPCIdentity, NPCState, SecretState
from epos.domain.outfit import OutfitItem, OutfitState
from epos.domain.player import PlayerState
from epos.domain.psychology import EmotionalState
from epos.domain.visual_state import VisualState
from epos.domain.world_state import LocationState, WorldState


def _outfit(item_id: str, name: str, color: str) -> OutfitState:
    return OutfitState(
        items=(
            OutfitItem(
                item_id=item_id,
                name=name,
                slot="body",
                layer=0,
                coverage=("torso",),
                color=color,
            ),
        )
    )


def _world() -> WorldState:
    player = PlayerState(
        entity_id=EntityId("player"),
        name="Player",
        location_id=LocationId("pool"),
        outfit=_outfit("player_shirt", "linen shirt", "blue"),
        visual_state=VisualState(traits={"wet_hair": True}),
        knowledge=KnowledgeState(facts={"private_player_fact": "hidden"}),
    )
    victoria = NPCState(
        identity=NPCIdentity(
            entity_id=EntityId("victoria"),
            name="Victoria",
            role="resort_director",
        ),
        location_id=LocationId("pool"),
        outfit=_outfit("victoria_dress", "summer dress", "white"),
        visual_state=VisualState(
            traits={"wet_clothes": False, "posture": "standing"}
        ),
        emotional_state=EmotionalState(joy=2, anger=8),
        knowledge=KnowledgeState(facts={"office_code": "4172"}),
        beliefs=KnowledgeState(facts={"rumor": "private belief"}),
        secrets=(
            SecretState(
                secret_id="letter",
                fact="The letter is in the office safe.",
            ),
        ),
    )
    theron = NPCState(
        identity=NPCIdentity(
            entity_id=EntityId("theron"),
            name="Theron",
            role="guard",
        ),
        location_id=LocationId("lobby"),
        outfit=_outfit("theron_armor", "bronze armor", "bronze"),
    )
    return WorldState(
        session_id=SessionId("session-visual"),
        worldpack_id=WorldpackId("resort-world"),
        turn_number=12,
        day=3,
        world_phase="sunset",
        player=player,
        npcs={
            EntityId("victoria"): victoria,
            EntityId("theron"): theron,
        },
        locations={
            LocationId("pool"): LocationState(
                location_id=LocationId("pool"),
                name="Pool",
            ),
            LocationId("lobby"): LocationState(
                location_id=LocationId("lobby"),
                name="Lobby",
            ),
        },
        world_truth=KnowledgeState(facts={"killer_identity": "secret world truth"}),
    )


def _resolved_check() -> ResolvedCheck:
    return ResolvedCheck(
        skill_id=SkillId("negoziazione"),
        difficulty=4,
        rating=3,
        pool_size=3,
        dice=(6, 4, 2),
        success_count=2,
        outcome=CheckOutcome.FULL_SUCCESS,
    )


def _scene_input() -> SceneObservationInput:
    return SceneObservationInput(
        action=ValidatedAction(
            intent="persuasion",
            target_ids=(EntityId("victoria"),),
            check=CheckProposal(
                skill_id=SkillId("negoziazione"),
                difficulty=4,
            ),
            skill_rating=3,
        ),
        resolved_check=_resolved_check(),
        subject_cues=(
            SceneSubjectCue(
                entity_id=EntityId("victoria"),
                position="pool_edge",
                mood_expressions=("tense", "controlled"),
            ),
        ),
        observable_consequences=(
            ObservableConsequence(
                consequence_id="access_granted",
                kind="social_result",
                fact="Victoria visibly relaxes and steps aside.",
                subject_ids=(EntityId("victoria"),),
            ),
        ),
    )


def test_builder_creates_one_local_authoritative_scene() -> None:
    state = _world()
    before = deepcopy(state)

    scene = ObservableSceneBuilder().build(state=state, observation=_scene_input())

    assert scene.scene_id == "session-visual:12"
    assert scene.location.location_id == LocationId("pool")
    assert scene.location.name == "Pool"
    assert scene.time.turn_number == 12
    assert scene.time.day == 3
    assert scene.time.world_phase == "sunset"
    assert tuple(subject.entity_id for subject in scene.visible_subjects) == (
        EntityId("player"),
        EntityId("victoria"),
    )
    assert scene.visible_subjects[0].kind is SubjectKind.PLAYER
    assert scene.visible_subjects[1].kind is SubjectKind.NPC
    assert scene.visible_subjects[1].role == "resort_director"
    assert scene.visible_subjects[1].position == "pool_edge"
    assert scene.visible_subjects[1].mood_expressions == ("tense", "controlled")
    assert state == before


def test_outfit_and_visual_state_are_copied_from_worldstate_not_observation() -> None:
    state = _world()
    scene = ObservableSceneBuilder().build(state=state, observation=_scene_input())
    victoria = next(
        subject
        for subject in scene.visible_subjects
        if subject.entity_id == EntityId("victoria")
    )

    assert victoria.outfit == state.get_npc(EntityId("victoria")).outfit
    assert victoria.visual_state == state.get_npc(EntityId("victoria")).visual_state
    assert victoria.outfit.items[0].name == "summer dress"
    assert victoria.outfit.items[0].color == "white"
    assert victoria.visual_state.traits["posture"] == "standing"


def test_private_world_and_npc_state_never_enters_observable_scene_payload() -> None:
    scene = ObservableSceneBuilder().build(state=_world(), observation=_scene_input())
    payload = scene.model_dump_json()

    assert "killer_identity" not in payload
    assert "secret world truth" not in payload
    assert "office_code" not in payload
    assert "4172" not in payload
    assert "private belief" not in payload
    assert "letter" not in payload
    assert "office safe" not in payload
    assert "private_player_fact" not in payload


def test_remote_subject_cue_is_rejected_instead_of_teleporting_npc() -> None:
    observation = _scene_input().model_copy(
        update={
            "subject_cues": (
                SceneSubjectCue(
                    entity_id=EntityId("theron"),
                    position="beside_player",
                ),
            )
        }
    )

    with pytest.raises(ObservableSceneValidationError, match="visible"):
        ObservableSceneBuilder().build(state=_world(), observation=observation)


def test_consequence_referencing_remote_subject_is_rejected() -> None:
    observation = _scene_input().model_copy(
        update={
            "observable_consequences": (
                ObservableConsequence(
                    consequence_id="remote_wave",
                    kind="gesture",
                    fact="Theron waves from elsewhere.",
                    subject_ids=(EntityId("theron"),),
                ),
            )
        }
    )

    with pytest.raises(ObservableSceneValidationError, match="visible"):
        ObservableSceneBuilder().build(state=_world(), observation=observation)


def test_visual_focus_candidate_is_derived_only_from_local_action_targets() -> None:
    scene = ObservableSceneBuilder().build(state=_world(), observation=_scene_input())

    assert scene.visual_focus_candidate is not None
    assert scene.visual_focus_candidate.subject_ids == (EntityId("victoria"),)
    assert scene.visual_focus_candidate.reason == "action_target"


def test_resolved_action_check_and_observable_consequences_are_preserved() -> None:
    scene = ObservableSceneBuilder().build(state=_world(), observation=_scene_input())

    assert scene.resolved_action.action.intent == "persuasion"
    assert scene.resolved_action.resolved_check == _resolved_check()
    assert scene.observable_consequences[0].consequence_id == "access_granted"
    assert (
        scene.observable_consequences[0].fact
        == "Victoria visibly relaxes and steps aside."
    )


def test_authorized_dialogue_enrichment_keeps_same_canonical_moment() -> None:
    builder = ObservableSceneBuilder()
    base = builder.build(state=_world(), observation=_scene_input())

    enriched = builder.attach_authorized_dialogue(
        scene=base,
        dialogue=(
            AuthorizedDialogueLine(
                speaker_id=EntityId("victoria"),
                target_ids=(EntityId("player"),),
                text="Va bene. Puoi passare.",
            ),
        ),
    )

    assert base.authorized_dialogue == ()
    assert enriched.scene_id == base.scene_id
    assert enriched.location == base.location
    assert enriched.time == base.time
    assert enriched.visible_subjects == base.visible_subjects
    assert enriched.resolved_action == base.resolved_action
    assert enriched.observable_consequences == base.observable_consequences
    assert enriched.authorized_dialogue[0].speaker_id == EntityId("victoria")


def test_dialogue_from_remote_or_player_speaker_is_rejected() -> None:
    builder = ObservableSceneBuilder()
    scene = builder.build(state=_world(), observation=_scene_input())

    for speaker_id in (EntityId("theron"), EntityId("player")):
        with pytest.raises(ObservableSceneValidationError, match="dialogue"):
            builder.attach_authorized_dialogue(
                scene=scene,
                dialogue=(
                    AuthorizedDialogueLine(
                        speaker_id=speaker_id,
                        target_ids=(EntityId("victoria"),),
                        text="Not authorized.",
                    ),
                ),
            )

from __future__ import annotations

from epos.application.actions.models import ValidatedAction
from epos.application.visual import ObservableSceneBuilder, SceneObservationInput
from epos.domain.ids import EntityId, LocationId, SessionId, TurnNumber, WorldpackId
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, WorldState


def _state() -> WorldState:
    lobby = LocationId("loc_lobby")
    return WorldState(
        session_id=SessionId("session"),
        worldpack_id=WorldpackId("resort_world"),
        turn_number=TurnNumber(4),
        day=1,
        world_phase="mattina",
        player=PlayerState(
            entity_id=EntityId("player"),
            name="Protagonista",
            location_id=lobby,
        ),
        npcs={
            EntityId("victoria"): NPCState(
                identity=NPCIdentity(
                    entity_id=EntityId("victoria"),
                    name="Victoria Hale",
                    role="vip_director",
                ),
                location_id=lobby,
            ),
            EntityId("stella"): NPCState(
                identity=NPCIdentity(
                    entity_id=EntityId("stella"),
                    name="Stella",
                    role="vip_entertainer",
                ),
                location_id=lobby,
            ),
            EntityId("maria"): NPCState(
                identity=NPCIdentity(
                    entity_id=EntityId("maria"),
                    name="Maria",
                    role="suite_attendant",
                ),
                location_id=lobby,
            ),
        },
        locations={lobby: LocationState(location_id=lobby, name="Lobby")},
    )


def test_targeted_greeting_renders_only_player_and_target_npc() -> None:
    scene = ObservableSceneBuilder().build(
        state=_state(),
        observation=SceneObservationInput(
            action=ValidatedAction(
                intent="greeting",
                target_ids=(EntityId("victoria"),),
            )
        ),
    )

    assert tuple(subject.entity_id for subject in scene.visible_subjects) == (
        EntityId("player"),
        EntityId("victoria"),
    )
    assert scene.visual_focus_candidate is not None
    assert scene.visual_focus_candidate.subject_ids == (EntityId("victoria"),)


def test_visual_scene_never_exposes_role_placeholder_as_player_personal_name() -> None:
    scene = ObservableSceneBuilder().build(
        state=_state(),
        observation=SceneObservationInput(
            action=ValidatedAction(
                intent="greeting",
                target_ids=(EntityId("victoria"),),
            )
        ),
    )

    player = scene.visible_subjects[0]
    assert player.entity_id == EntityId("player")
    assert player.name == "player"
    assert player.name != "Protagonista"


def test_untargeted_social_scene_keeps_all_local_npcs_available() -> None:
    scene = ObservableSceneBuilder().build(
        state=_state(),
        observation=SceneObservationInput(
            action=ValidatedAction(intent="greeting")
        ),
    )

    assert tuple(subject.entity_id for subject in scene.visible_subjects) == (
        EntityId("player"),
        EntityId("maria"),
        EntityId("stella"),
        EntityId("victoria"),
    )

from copy import deepcopy

import pytest
from pydantic import ValidationError

from epos.domain.ids import EntityId, LocationId, SessionId, WorldpackId
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, WorldState


def build_world() -> WorldState:
    player = PlayerState(
        entity_id=EntityId("player"),
        name="Player",
        location_id=LocationId("lobby"),
        knowledge={"facts": {"visible_fact": "known"}},
    )
    npc = NPCState(
        identity=NPCIdentity(entity_id=EntityId("victoria"), name="Victoria", role="director"),
        location_id=LocationId("lobby"),
        personality=("controlled", "strategic"),
        speech_style="measured",
    )
    return WorldState(
        session_id=SessionId("session-1"),
        worldpack_id=WorldpackId("test-world"),
        turn_number=0,
        day=1,
        world_phase="morning",
        player=player,
        npcs={npc.identity.entity_id: npc},
        locations={
            LocationId("lobby"): LocationState(location_id=LocationId("lobby"), name="Lobby")
        },
        world_truth={"facts": {"secret_fact": "true", "visible_fact": "known"}},
    )


def test_world_state_round_trip_preserves_typed_content() -> None:
    world = build_world()
    restored = WorldState.model_validate_json(world.model_dump_json())

    assert restored == world
    assert restored.get_npc(EntityId("victoria")).identity.name == "Victoria"


def test_world_state_forbids_unknown_fields() -> None:
    payload = build_world().model_dump(mode="python")
    payload["surprise"] = True

    with pytest.raises(ValidationError):
        WorldState.model_validate(payload)


def test_player_knowledge_is_separate_from_world_truth() -> None:
    world = build_world()

    assert "secret_fact" in world.world_truth.facts
    assert "secret_fact" not in world.player.knowledge.facts


def test_deepcopy_does_not_mutate_authoritative_state() -> None:
    world = build_world()
    candidate = deepcopy(world)

    candidate.day = 2
    candidate.player.name = "Changed"

    assert world.day == 1
    assert world.player.name == "Player"

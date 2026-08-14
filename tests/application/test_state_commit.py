from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from epos.application.state import (
    AuthoritativeStateManager,
    MutationAuthority,
    MutationAuthorityError,
    MutationBatch,
    SetNPCIntentionsMutation,
    SetPlayerLocationMutation,
    SetWorldFlagMutation,
    StateMutationError,
)
from epos.domain.errors import PersistenceError
from epos.domain.ids import EntityId, LocationId, SessionId, WorldpackId
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, WorldState


def _world() -> WorldState:
    player = PlayerState(
        entity_id=EntityId("player"),
        name="Player",
        location_id=LocationId("lobby"),
    )
    victoria = NPCState(
        identity=NPCIdentity(
            entity_id=EntityId("victoria"),
            name="Victoria",
            role="director",
        ),
        location_id=LocationId("lobby"),
    )
    return WorldState(
        session_id=SessionId("session-1"),
        worldpack_id=WorldpackId("test-world"),
        turn_number=3,
        day=1,
        world_phase="morning",
        player=player,
        npcs={EntityId("victoria"): victoria},
        locations={
            LocationId("lobby"): LocationState(
                location_id=LocationId("lobby"),
                name="Lobby",
            ),
            LocationId("garden"): LocationState(
                location_id=LocationId("garden"),
                name="Garden",
            ),
        },
    )


class RecordingStateStore:
    def __init__(self, state: WorldState, *, fail_save: bool = False) -> None:
        self.loaded = state.model_copy(deep=True)
        self.fail_save = fail_save
        self.saved: list[WorldState] = []

    async def load(self, session_id: SessionId) -> WorldState:
        assert session_id == self.loaded.session_id
        return self.loaded.model_copy(deep=True)

    async def save(self, session_id: SessionId, state: WorldState) -> None:
        assert session_id == state.session_id
        if self.fail_save:
            raise PersistenceError("simulated persistence failure")
        self.saved.append(state.model_copy(deep=True))


@pytest.mark.asyncio
async def test_commit_uses_copy_persists_then_swaps_authoritative_state() -> None:
    original = _world()
    original_before = deepcopy(original)
    store = RecordingStateStore(original)
    manager = AuthoritativeStateManager(initial_state=original, state_store=store)

    committed = await manager.commit(
        MutationBatch(
            producer=MutationAuthority.ENGINE_ONLY,
            mutations=(SetWorldFlagMutation(key="door_open", value=True),),
        )
    )

    assert original == original_before
    assert original.flags == {}
    assert committed.flags == {"door_open": True}
    assert manager.snapshot().flags == {"door_open": True}
    assert store.saved == [committed]


@pytest.mark.asyncio
async def test_failed_persistence_never_swaps_live_state() -> None:
    original = _world()
    store = RecordingStateStore(original, fail_save=True)
    manager = AuthoritativeStateManager(initial_state=original, state_store=store)

    with pytest.raises(PersistenceError, match="simulated"):
        await manager.commit(
            MutationBatch(
                producer=MutationAuthority.ENGINE_ONLY,
                mutations=(SetWorldFlagMutation(key="door_open", value=True),),
            )
        )

    assert manager.snapshot() == original
    assert manager.snapshot().flags == {}


@pytest.mark.asyncio
async def test_invalid_resulting_world_is_rejected_before_persistence() -> None:
    original = _world()
    store = RecordingStateStore(original)
    manager = AuthoritativeStateManager(initial_state=original, state_store=store)

    with pytest.raises(StateMutationError, match="location"):
        await manager.commit(
            MutationBatch(
                producer=MutationAuthority.ENGINE_ONLY,
                mutations=(
                    SetPlayerLocationMutation(destination_id=LocationId("missing")),
                ),
            )
        )

    assert store.saved == []
    assert manager.snapshot() == original


@pytest.mark.asyncio
async def test_mutation_authority_is_enforced_before_apply() -> None:
    original = _world()
    store = RecordingStateStore(original)
    manager = AuthoritativeStateManager(initial_state=original, state_store=store)

    with pytest.raises(MutationAuthorityError, match="authority"):
        await manager.commit(
            MutationBatch(
                producer=MutationAuthority.LLM_PROPOSABLE,
                mutations=(SetWorldFlagMutation(key="hacked", value=True),),
            )
        )

    assert manager.snapshot() == original
    assert store.saved == []


@pytest.mark.asyncio
async def test_llm_proposable_mutation_can_only_change_its_typed_field() -> None:
    original = _world()
    store = RecordingStateStore(original)
    manager = AuthoritativeStateManager(initial_state=original, state_store=store)

    committed = await manager.commit(
        MutationBatch(
            producer=MutationAuthority.LLM_PROPOSABLE,
            mutations=(
                SetNPCIntentionsMutation(
                    npc_id=EntityId("victoria"),
                    intentions=("continue_conversation",),
                ),
            ),
        )
    )

    assert committed.get_npc(EntityId("victoria")).intentions == (
        "continue_conversation",
    )
    assert committed.player == original.player


def test_mutation_union_forbids_extra_payload_fields() -> None:
    with pytest.raises(ValidationError):
        MutationBatch.model_validate(
            {
                "producer": "engine_only",
                "mutations": [
                    {
                        "kind": "set_world_flag",
                        "key": "door_open",
                        "value": True,
                        "invented": "not allowed",
                    }
                ],
            }
        )

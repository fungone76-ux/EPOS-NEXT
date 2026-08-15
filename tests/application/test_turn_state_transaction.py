from __future__ import annotations

import pytest

from epos.application.state import (
    AdvanceTurnMutation,
    AuthoritativeStateManager,
    MutationAuthority,
    MutationBatch,
    SetNPCIntentionsMutation,
    SetWorldFlagMutation,
    StateMutationError,
)
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
            )
        },
    )


class RecordingStore:
    def __init__(self, state: WorldState) -> None:
        self.loaded = state.model_copy(deep=True)
        self.saved: list[WorldState] = []

    async def load(self, session_id: SessionId) -> WorldState:
        assert session_id == self.loaded.session_id
        return self.loaded.model_copy(deep=True)

    async def save(self, session_id: SessionId, state: WorldState) -> None:
        assert session_id == state.session_id
        self.loaded = state.model_copy(deep=True)
        self.saved.append(state.model_copy(deep=True))


@pytest.mark.asyncio
async def test_turn_transaction_commits_multiple_authorities_with_one_save_and_swap() -> None:
    original = _world()
    store = RecordingStore(original)
    manager = AuthoritativeStateManager(initial_state=original, state_store=store)

    committed = await manager.commit_many(
        (
            MutationBatch(
                producer=MutationAuthority.ENGINE_ONLY,
                mutations=(SetWorldFlagMutation(key="door_open", value=True),),
            ),
            MutationBatch(
                producer=MutationAuthority.LLM_PROPOSABLE,
                mutations=(
                    SetNPCIntentionsMutation(
                        npc_id=EntityId("victoria"),
                        intentions=("continue_conversation",),
                    ),
                ),
            ),
            MutationBatch(
                producer=MutationAuthority.ENGINE_ONLY,
                mutations=(AdvanceTurnMutation(),),
            ),
        )
    )

    assert len(store.saved) == 1
    assert committed.flags == {"door_open": True}
    assert committed.npcs[EntityId("victoria")].intentions == (
        "continue_conversation",
    )
    assert int(committed.turn_number) == 4
    assert manager.snapshot() == committed


@pytest.mark.asyncio
async def test_turn_transaction_rejects_late_invalid_batch_without_partial_save_or_swap() -> None:
    original = _world()
    store = RecordingStore(original)
    manager = AuthoritativeStateManager(initial_state=original, state_store=store)

    with pytest.raises(StateMutationError, match="unknown npc"):
        await manager.commit_many(
            (
                MutationBatch(
                    producer=MutationAuthority.ENGINE_ONLY,
                    mutations=(SetWorldFlagMutation(key="would_be_partial", value=True),),
                ),
                MutationBatch(
                    producer=MutationAuthority.LLM_PROPOSABLE,
                    mutations=(
                        SetNPCIntentionsMutation(
                            npc_id=EntityId("missing"),
                            intentions=("invalid",),
                        ),
                    ),
                ),
            )
        )

    assert store.saved == []
    assert manager.snapshot() == original


def test_turn_advance_is_engine_only_and_has_no_time_side_effect() -> None:
    mutation = AdvanceTurnMutation()
    assert mutation.authority is MutationAuthority.ENGINE_ONLY
    assert mutation.kind == "advance_turn"

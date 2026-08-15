from __future__ import annotations

import pytest

from epos.application.state import (
    AdvanceTurnMutation,
    AuthoritativeStateManager,
    MutationAuthority,
    MutationBatch,
    ReplaceNPCBondStateMutation,
    SetNPCIntentionsMutation,
    SetWorldFlagMutation,
    StaleAuthoritativeStateError,
    StateMutationError,
)
from epos.domain.bond import BondPhase, BondState
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
                mutations=(
                    ReplaceNPCBondStateMutation(
                        npc_id=EntityId("victoria"),
                        bond_state=BondState(phase=BondPhase.FORMING),
                    ),
                    AdvanceTurnMutation(),
                ),
            ),
        ),
        expected_state=original,
    )

    assert len(store.saved) == 1
    assert committed.flags == {"door_open": True}
    assert committed.npcs[EntityId("victoria")].intentions == (
        "continue_conversation",
    )
    assert committed.npcs[EntityId("victoria")].bond_state.phase is BondPhase.FORMING
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
            ),
            expected_state=original,
        )

    assert store.saved == []
    assert manager.snapshot() == original


@pytest.mark.asyncio
async def test_stale_turn_plan_cannot_commit_over_newer_authoritative_state() -> None:
    original = _world()
    store = RecordingStore(original)
    manager = AuthoritativeStateManager(initial_state=original, state_store=store)
    pre_turn = manager.snapshot()

    await manager.commit(
        MutationBatch(
            producer=MutationAuthority.ENGINE_ONLY,
            mutations=(SetWorldFlagMutation(key="other_writer", value=True),),
        )
    )
    saves_before_stale_attempt = len(store.saved)

    with pytest.raises(StaleAuthoritativeStateError, match="changed while turn was planned"):
        await manager.commit_many(
            (
                MutationBatch(
                    producer=MutationAuthority.ENGINE_ONLY,
                    mutations=(SetWorldFlagMutation(key="stale_plan", value=True),),
                ),
            ),
            expected_state=pre_turn,
        )

    assert len(store.saved) == saves_before_stale_attempt
    current = manager.snapshot()
    assert current.flags == {"other_writer": True}


def test_turn_advance_and_bond_replacement_are_engine_only() -> None:
    turn = AdvanceTurnMutation()
    bond = ReplaceNPCBondStateMutation(
        npc_id=EntityId("victoria"),
        bond_state=BondState(phase=BondPhase.ESTABLISHED),
    )
    assert turn.authority is MutationAuthority.ENGINE_ONLY
    assert turn.kind == "advance_turn"
    assert bond.authority is MutationAuthority.ENGINE_ONLY
    assert bond.kind == "replace_npc_bond_state"

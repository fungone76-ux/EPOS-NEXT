from __future__ import annotations

import pytest
from pydantic import ValidationError

from epos.application.actions.models import (
    CheckOutcome,
    CheckProposal,
    ResolvedCheck,
    ValidatedAction,
)
from epos.application.state import (
    CheckpointStateMismatchError,
    DiceCheckpoint,
    DiceCheckpointService,
    StateReference,
)
from epos.domain.ids import EntityId, LocationId, SessionId, SkillId, WorldpackId
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, WorldState


def _world(*, day: int = 1) -> WorldState:
    player = PlayerState(
        entity_id=EntityId("player"),
        name="Player",
        location_id=LocationId("lobby"),
    )
    npc = NPCState(
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
        turn_number=8,
        day=day,
        world_phase="morning",
        player=player,
        npcs={EntityId("victoria"): npc},
        locations={
            LocationId("lobby"): LocationState(
                location_id=LocationId("lobby"),
                name="Lobby",
            )
        },
    )


def _proposal() -> CheckProposal:
    return CheckProposal(skill_id=SkillId("negoziazione"), difficulty=4)


def _action() -> ValidatedAction:
    return ValidatedAction(
        intent="persuade",
        target_ids=(EntityId("victoria"),),
        check=_proposal(),
        skill_rating=3,
    )


class MemoryCheckpointStore:
    def __init__(self) -> None:
        self.value: DiceCheckpoint | None = None

    async def save(self, checkpoint: DiceCheckpoint) -> None:
        self.value = checkpoint.model_copy(deep=True)

    async def load(self, session_id: SessionId) -> DiceCheckpoint | None:
        if self.value is None or self.value.session_id != session_id:
            return None
        return self.value.model_copy(deep=True)

    async def delete(self, session_id: SessionId) -> None:
        if self.value is not None and self.value.session_id == session_id:
            self.value = None


@pytest.mark.asyncio
async def test_checkpoint_preserves_exact_roll_and_turn_context_for_resume() -> None:
    state = _world()
    store = MemoryCheckpointStore()
    service = DiceCheckpointService(store=store)
    proposal = _proposal()
    resolved = ResolvedCheck(
        skill_id=SkillId("negoziazione"),
        difficulty=4,
        rating=3,
        pool_size=3,
        dice=(1, 4, 3),
        success_count=1,
        outcome=CheckOutcome.PARTIAL_SUCCESS,
    )

    saved = await service.save_after_roll(
        state=state,
        player_input="Convincila.",
        validated_action=_action(),
        proposal=proposal,
        resolved_check=resolved,
        player_decision="roll",
    )
    resumed = await service.resume(state=state)

    assert resumed == saved
    assert resumed is not None
    assert resumed.player_input == "Convincila."
    assert resumed.validated_action == _action()
    assert resumed.proposal == proposal
    assert resumed.resolved_check.pool_size == 3
    assert resumed.resolved_check.dice == (1, 4, 3)
    assert resumed.resolved_check.outcome is CheckOutcome.PARTIAL_SUCCESS
    assert resumed.player_decision == "roll"


def test_checkpoint_rejects_inconsistent_proposal_and_exact_roll() -> None:
    with pytest.raises(ValidationError):
        DiceCheckpoint(
            session_id=SessionId("session-1"),
            state_reference=StateReference(
                session_id=SessionId("session-1"),
                turn_number=8,
                fingerprint="a" * 64,
            ),
            player_input="Convincila.",
            validated_action=_action(),
            proposal=_proposal(),
            resolved_check=ResolvedCheck(
                skill_id=SkillId("negoziazione"),
                difficulty=5,
                rating=3,
                pool_size=3,
                dice=(1, 5, 2),
                success_count=1,
                outcome=CheckOutcome.PARTIAL_SUCCESS,
            ),
            player_decision="roll",
        )


@pytest.mark.asyncio
async def test_resume_rejects_checkpoint_from_different_state_snapshot() -> None:
    store = MemoryCheckpointStore()
    service = DiceCheckpointService(store=store)
    original = _world(day=1)
    proposal = _proposal()
    resolved = ResolvedCheck(
        skill_id=SkillId("negoziazione"),
        difficulty=4,
        rating=3,
        pool_size=3,
        dice=(6, 2, 1),
        success_count=1,
        outcome=CheckOutcome.PARTIAL_SUCCESS,
    )
    await service.save_after_roll(
        state=original,
        player_input="Convincila.",
        validated_action=_action(),
        proposal=proposal,
        resolved_check=resolved,
        player_decision="roll",
    )

    with pytest.raises(CheckpointStateMismatchError, match="state reference"):
        await service.resume(state=_world(day=2))

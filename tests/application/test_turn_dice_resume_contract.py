from __future__ import annotations

import pytest
from pydantic import ValidationError

from epos.application.actions.models import (
    CheckOutcome,
    CheckProposal,
    ResolvedCheck,
    ValidatedAction,
)
from epos.application.state import DiceCheckpoint, DiceCheckpointService, StateReference
from epos.domain.ids import EntityId, LocationId, SessionId, SkillId, WorldpackId
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, WorldState


def _world() -> WorldState:
    return WorldState(
        session_id=SessionId("session-1"),
        worldpack_id=WorldpackId("test-world"),
        turn_number=8,
        day=1,
        world_phase="morning",
        player=PlayerState(
            entity_id=EntityId("player"),
            name="Player",
            location_id=LocationId("lobby"),
        ),
        npcs={
            EntityId("victoria"): NPCState(
                identity=NPCIdentity(
                    entity_id=EntityId("victoria"),
                    name="Victoria",
                    role="director",
                ),
                location_id=LocationId("lobby"),
            )
        },
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


def _resolved() -> ResolvedCheck:
    return ResolvedCheck(
        skill_id=SkillId("negoziazione"),
        difficulty=4,
        rating=3,
        pool_size=3,
        dice=(1, 4, 6),
        success_count=2,
        outcome=CheckOutcome.FULL_SUCCESS,
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
async def test_checkpoint_preserves_player_input_and_validated_action_for_exact_resume() -> None:
    store = MemoryCheckpointStore()
    service = DiceCheckpointService(store=store)

    saved = await service.save_after_roll(
        state=_world(),
        player_input="Convincila a lasciarmi entrare.",
        validated_action=_action(),
        proposal=_proposal(),
        resolved_check=_resolved(),
        player_decision="roll",
    )
    resumed = await service.resume(state=_world())

    assert resumed == saved
    assert resumed is not None
    assert resumed.player_input == "Convincila a lasciarmi entrare."
    assert resumed.validated_action == _action()
    assert resumed.validated_action.check == resumed.proposal
    assert resumed.resolved_check == _resolved()


def test_checkpoint_rejects_action_that_does_not_own_saved_check() -> None:
    with pytest.raises(ValidationError, match="validated action"):
        DiceCheckpoint(
            session_id=SessionId("session-1"),
            state_reference=StateReference(
                session_id=SessionId("session-1"),
                turn_number=8,
                fingerprint="a" * 64,
            ),
            player_input="Convincila.",
            validated_action=ValidatedAction(intent="observe"),
            proposal=_proposal(),
            resolved_check=_resolved(),
            player_decision="roll",
        )

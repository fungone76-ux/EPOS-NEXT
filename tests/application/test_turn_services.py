from __future__ import annotations

import pytest

from epos.application.actions.models import (
    CheckOutcome,
    CheckProposal,
    MovementProposal,
    OutfitRequestProposal,
    ResolvedCheck,
    ValidatedAction,
)
from epos.application.psychology import (
    PsychologicalEvent,
    PsychologicalEventType,
    PsychologyProfile,
    PsychologyService,
)
from epos.application.state import (
    MutationAuthority,
    ReplaceNPCBondStateMutation,
    ReplaceNPCRelationshipMutation,
    SetPlayerLocationMutation,
)
from epos.application.turn import (
    CheckDecision,
    DefaultTurnActionResolver,
    PythonTurnPsychologyPlanner,
    TargetedPsychologicalEvent,
    TurnOrchestrationError,
)
from epos.domain.bond import BondPhase, BondState
from epos.domain.ids import EntityId, LocationId, SessionId, SkillId, WorldpackId
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, WorldState


def _world() -> WorldState:
    return WorldState(
        session_id=SessionId("session-1"),
        worldpack_id=WorldpackId("test-world"),
        turn_number=4,
        day=2,
        world_phase="afternoon",
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
            ),
            EntityId("stella"): NPCState(
                identity=NPCIdentity(
                    entity_id=EntityId("stella"),
                    name="Stella",
                    role="guest",
                ),
                location_id=LocationId("garden"),
            ),
        },
        locations={
            LocationId("lobby"): LocationState(
                location_id=LocationId("lobby"), name="Lobby"
            ),
            LocationId("garden"): LocationState(
                location_id=LocationId("garden"), name="Garden"
            ),
        },
    )


def test_declining_checked_action_does_not_apply_its_authoritative_movement() -> None:
    action = ValidatedAction(
        intent="sneak_to_garden",
        movement=MovementProposal(destination_id=LocationId("garden")),
        check=CheckProposal(skill_id=SkillId("furtivita"), difficulty=4),
        skill_rating=3,
    )

    result = DefaultTurnActionResolver().resolve(
        state=_world(),
        action=action,
        check_decision=CheckDecision.DECLINE,
        resolved_check=None,
    )

    assert result.mutation_batches == ()


def test_unchecked_movement_becomes_engine_only_location_mutation() -> None:
    action = ValidatedAction(
        intent="walk",
        movement=MovementProposal(destination_id=LocationId("garden")),
    )

    result = DefaultTurnActionResolver().resolve(
        state=_world(),
        action=action,
        check_decision=None,
        resolved_check=None,
    )

    assert len(result.mutation_batches) == 1
    batch = result.mutation_batches[0]
    assert batch.producer is MutationAuthority.ENGINE_ONLY
    assert batch.mutations == (
        SetPlayerLocationMutation(destination_id=LocationId("garden")),
    )


def test_outfit_request_requires_explicit_worldpack_resolution_policy() -> None:
    action = ValidatedAction(
        intent="change_outfit",
        outfit_request=OutfitRequestProposal(
            target_id=EntityId("player"),
            item_id="linen_shirt",
            requested_state="wear",
        ),
    )

    with pytest.raises(TurnOrchestrationError) as exc_info:
        DefaultTurnActionResolver().resolve(
            state=_world(),
            action=action,
            check_decision=None,
            resolved_check=None,
        )

    assert exc_info.value.code == "turn.action.unsupported_outfit_request"


def test_checked_movement_requires_explicit_outcome_to_mutation_policy() -> None:
    action = ValidatedAction(
        intent="sneak_to_garden",
        movement=MovementProposal(destination_id=LocationId("garden")),
        check=CheckProposal(skill_id=SkillId("furtivita"), difficulty=4),
        skill_rating=3,
    )
    resolved = ResolvedCheck(
        skill_id=SkillId("furtivita"),
        difficulty=4,
        rating=3,
        pool_size=3,
        dice=(6, 4, 2),
        success_count=2,
        outcome=CheckOutcome.FULL_SUCCESS,
    )

    with pytest.raises(TurnOrchestrationError) as exc_info:
        DefaultTurnActionResolver().resolve(
            state=_world(),
            action=action,
            check_decision=CheckDecision.ROLL,
            resolved_check=resolved,
        )

    assert exc_info.value.code == "turn.action.checked_movement_requires_policy"


class PraiseVictoriaEvents:
    def events_for(self, **kwargs):
        return (
            TargetedPsychologicalEvent(
                npc_id=EntityId("victoria"),
                event=PsychologicalEvent(
                    event_type=PsychologicalEventType.PRAISE,
                    intensity=1.0,
                ),
            ),
        )


class OffsceneStellaEvents:
    def events_for(self, **kwargs):
        return (
            TargetedPsychologicalEvent(
                npc_id=EntityId("stella"),
                event=PsychologicalEvent(
                    event_type=PsychologicalEventType.PRAISE,
                    intensity=1.0,
                ),
            ),
        )


class DefaultProfiles:
    def profile_for(self, npc_id: EntityId) -> PsychologyProfile:
        return PsychologyProfile()


class RecordingBondPolicy:
    def __init__(self) -> None:
        self.contexts = []

    def derive(self, context):
        self.contexts.append(context.model_copy(deep=True))
        return BondState(phase=BondPhase.FORMING)


def test_python_psychology_updates_relationship_before_bond_derivation() -> None:
    bond = RecordingBondPolicy()
    planner = PythonTurnPsychologyPlanner(
        psychology=PsychologyService.default(),
        event_source=PraiseVictoriaEvents(),
        profiles=DefaultProfiles(),
        bond_derivation=bond,
    )

    plan = planner.plan(
        state=_world(),
        action=ValidatedAction(intent="praise", target_ids=(EntityId("victoria"),)),
        resolved_check=None,
        present_npc_ids=(EntityId("victoria"),),
    )

    assert len(bond.contexts) == 1
    context = bond.contexts[0]
    assert context.npc_id == EntityId("victoria")
    assert context.relationship_with_player.affection > 0.0
    assert context.relationship_with_player.respect > 0.0
    assert context.event_types == (PsychologicalEventType.PRAISE.value,)
    assert all(batch.producer is MutationAuthority.ENGINE_ONLY for batch in plan.mutation_batches)
    mutations = tuple(
        mutation for batch in plan.mutation_batches for mutation in batch.mutations
    )
    assert any(isinstance(item, ReplaceNPCRelationshipMutation) for item in mutations)
    assert any(isinstance(item, ReplaceNPCBondStateMutation) for item in mutations)


def test_psychology_planner_rejects_event_for_offscene_npc() -> None:
    planner = PythonTurnPsychologyPlanner(
        psychology=PsychologyService.default(),
        event_source=OffsceneStellaEvents(),
        profiles=DefaultProfiles(),
        bond_derivation=RecordingBondPolicy(),
    )

    with pytest.raises(TurnOrchestrationError, match="off-scene NPC stella"):
        planner.plan(
            state=_world(),
            action=ValidatedAction(intent="praise", target_ids=(EntityId("victoria"),)),
            resolved_check=None,
            present_npc_ids=(EntityId("victoria"),),
        )

"""Pure application of validated state mutations to a detached WorldState copy."""

from __future__ import annotations

from typing import assert_never

from epos.application.state.errors import StateMutationError
from epos.application.state.models import (
    AdvanceTurnMutation,
    ReplaceNPCEmotionalStateMutation,
    ReplaceNPCRelationshipMutation,
    SetNPCIntentionsMutation,
    SetNPCLocationMutation,
    SetPlayerLocationMutation,
    SetWorldFlagMutation,
    SetWorldPhaseMutation,
    StateMutation,
)
from epos.domain.ids import TurnNumber
from epos.domain.world_state import WorldState


def apply_mutation(state: WorldState, mutation: StateMutation) -> None:
    """Mutate only a detached candidate state; never call this on the live state."""

    if isinstance(mutation, SetWorldFlagMutation):
        state.flags[mutation.key] = mutation.value
        return
    if isinstance(mutation, SetPlayerLocationMutation):
        state.player.location_id = mutation.destination_id
        return
    if isinstance(mutation, SetNPCLocationMutation):
        try:
            npc = state.npcs[mutation.npc_id]
        except KeyError as exc:
            raise StateMutationError(f"unknown npc {mutation.npc_id}") from exc
        npc.location_id = mutation.destination_id
        return
    if isinstance(mutation, SetNPCIntentionsMutation):
        try:
            npc = state.npcs[mutation.npc_id]
        except KeyError as exc:
            raise StateMutationError(f"unknown npc {mutation.npc_id}") from exc
        npc.intentions = mutation.intentions
        return
    if isinstance(mutation, ReplaceNPCEmotionalStateMutation):
        try:
            npc = state.npcs[mutation.npc_id]
        except KeyError as exc:
            raise StateMutationError(f"unknown npc {mutation.npc_id}") from exc
        npc.emotional_state = mutation.emotional_state.model_copy(deep=True)
        return
    if isinstance(mutation, ReplaceNPCRelationshipMutation):
        try:
            npc = state.npcs[mutation.npc_id]
        except KeyError as exc:
            raise StateMutationError(f"unknown npc {mutation.npc_id}") from exc
        npc.relationships[mutation.partner_id] = mutation.relationship.model_copy(deep=True)
        return
    if isinstance(mutation, SetWorldPhaseMutation):
        state.world_phase = mutation.world_phase
        return
    if isinstance(mutation, AdvanceTurnMutation):
        state.turn_number = TurnNumber(int(state.turn_number) + 1)
        return
    assert_never(mutation)

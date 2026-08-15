"""Typed state mutations and crash-recovery contracts for authoritative turns."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from epos.application.actions.models import CheckProposal, ResolvedCheck, ValidatedAction
from epos.domain.base import DomainModel
from epos.domain.bond import BondState
from epos.domain.ids import EntityId, LocationId, SessionId, TurnNumber
from epos.domain.memory import EmotionalMemoryState, MemoryEntryState
from epos.domain.outfit import OutfitState, WardrobeOutfit
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState


class MutationAuthority(StrEnum):
    """Origin allowed to propose a mutation type."""

    ENGINE_ONLY = "engine_only"
    LLM_PROPOSABLE = "llm_proposable"
    WORLDPACK_ONLY = "worldpack_only"


class SetWorldFlagMutation(DomainModel):
    kind: Literal["set_world_flag"] = "set_world_flag"
    authority: Literal[MutationAuthority.ENGINE_ONLY] = MutationAuthority.ENGINE_ONLY
    key: str
    value: bool

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("flag key must not be empty")
        return normalized


class SetPlayerLocationMutation(DomainModel):
    kind: Literal["set_player_location"] = "set_player_location"
    authority: Literal[MutationAuthority.ENGINE_ONLY] = MutationAuthority.ENGINE_ONLY
    destination_id: LocationId


class SetNPCLocationMutation(DomainModel):
    kind: Literal["set_npc_location"] = "set_npc_location"
    authority: Literal[MutationAuthority.ENGINE_ONLY] = MutationAuthority.ENGINE_ONLY
    npc_id: EntityId
    destination_id: LocationId


class SetNPCIntentionsMutation(DomainModel):
    kind: Literal["set_npc_intentions"] = "set_npc_intentions"
    authority: Literal[MutationAuthority.LLM_PROPOSABLE] = MutationAuthority.LLM_PROPOSABLE
    npc_id: EntityId
    intentions: tuple[str, ...] = ()

    @field_validator("intentions")
    @classmethod
    def validate_intentions(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("intentions must not contain empty values")
        return normalized


class ReplacePlayerOutfitMutation(DomainModel):
    kind: Literal["replace_player_outfit"] = "replace_player_outfit"
    authority: Literal[MutationAuthority.ENGINE_ONLY] = MutationAuthority.ENGINE_ONLY
    outfit: OutfitState


class ReplaceNPCOutfitMutation(DomainModel):
    kind: Literal["replace_npc_outfit"] = "replace_npc_outfit"
    authority: Literal[MutationAuthority.ENGINE_ONLY] = MutationAuthority.ENGINE_ONLY
    npc_id: EntityId
    outfit: OutfitState


class UpsertWardrobeOutfitMutation(DomainModel):
    """Persist one runtime-created canonical outfit for later reuse."""

    kind: Literal["upsert_wardrobe_outfit"] = "upsert_wardrobe_outfit"
    authority: Literal[MutationAuthority.ENGINE_ONLY] = MutationAuthority.ENGINE_ONLY
    outfit: WardrobeOutfit


class ReplaceNPCEmotionalStateMutation(DomainModel):
    kind: Literal["replace_npc_emotional_state"] = "replace_npc_emotional_state"
    authority: Literal[MutationAuthority.ENGINE_ONLY] = MutationAuthority.ENGINE_ONLY
    npc_id: EntityId
    emotional_state: EmotionalState


class ReplaceNPCRelationshipMutation(DomainModel):
    kind: Literal["replace_npc_relationship"] = "replace_npc_relationship"
    authority: Literal[MutationAuthority.ENGINE_ONLY] = MutationAuthority.ENGINE_ONLY
    npc_id: EntityId
    partner_id: EntityId
    relationship: RelationshipState


class ReplaceNPCBondStateMutation(DomainModel):
    kind: Literal["replace_npc_bond_state"] = "replace_npc_bond_state"
    authority: Literal[MutationAuthority.ENGINE_ONLY] = MutationAuthority.ENGINE_ONLY
    npc_id: EntityId
    bond_state: BondState


class ReplaceNPCMemoryLayersMutation(DomainModel):
    kind: Literal["replace_npc_memory_layers"] = "replace_npc_memory_layers"
    authority: Literal[MutationAuthority.ENGINE_ONLY] = MutationAuthority.ENGINE_ONLY
    npc_id: EntityId
    short_term_memory: tuple[MemoryEntryState, ...] = ()
    core_memories: tuple[MemoryEntryState, ...] = ()
    emotional_memory: tuple[EmotionalMemoryState, ...] = ()

    @field_validator("short_term_memory")
    @classmethod
    def validate_short_term_bound(
        cls,
        values: tuple[MemoryEntryState, ...],
    ) -> tuple[MemoryEntryState, ...]:
        if len(values) > 20:
            raise ValueError("short-term memory cannot exceed 20 entries")
        return values


class SetWorldPhaseMutation(DomainModel):
    kind: Literal["set_world_phase"] = "set_world_phase"
    authority: Literal[MutationAuthority.ENGINE_ONLY] = MutationAuthority.ENGINE_ONLY
    world_phase: str

    @field_validator("world_phase")
    @classmethod
    def validate_world_phase(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("world_phase must not be empty")
        return normalized


class AdvanceTurnMutation(DomainModel):
    """Advance only the canonical turn counter; GameTime remains independently owned."""

    kind: Literal["advance_turn"] = "advance_turn"
    authority: Literal[MutationAuthority.ENGINE_ONLY] = MutationAuthority.ENGINE_ONLY


StateMutation = Annotated[
    SetWorldFlagMutation
    | SetPlayerLocationMutation
    | SetNPCLocationMutation
    | SetNPCIntentionsMutation
    | ReplacePlayerOutfitMutation
    | ReplaceNPCOutfitMutation
    | UpsertWardrobeOutfitMutation
    | ReplaceNPCEmotionalStateMutation
    | ReplaceNPCRelationshipMutation
    | ReplaceNPCBondStateMutation
    | ReplaceNPCMemoryLayersMutation
    | SetWorldPhaseMutation
    | AdvanceTurnMutation,
    Field(discriminator="kind"),
]


class MutationBatch(DomainModel):
    """One origin-homogeneous mutation proposal awaiting Python authority checks."""

    producer: MutationAuthority
    mutations: tuple[StateMutation, ...]


class StateReference(DomainModel):
    """Stable reference to the exact authoritative state used when dice were rolled."""

    session_id: SessionId
    turn_number: TurnNumber
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class DiceCheckpoint(DomainModel):
    """Exact resumable turn payload persisted immediately after a Python dice roll."""

    session_id: SessionId
    state_reference: StateReference
    player_input: str
    validated_action: ValidatedAction
    proposal: CheckProposal
    resolved_check: ResolvedCheck
    player_decision: str

    @field_validator("player_input", "player_decision")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("checkpoint text fields must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_exact_roll_integrity(self) -> Self:
        if self.state_reference.session_id != self.session_id:
            raise ValueError("state reference session does not match checkpoint session")
        if self.validated_action.check != self.proposal:
            raise ValueError("validated action does not own checkpoint proposal")
        if self.validated_action.skill_rating != self.resolved_check.rating:
            raise ValueError("validated action rating does not match resolved check")
        if self.proposal.skill_id != self.resolved_check.skill_id:
            raise ValueError("resolved skill does not match check proposal")
        if self.proposal.difficulty != self.resolved_check.difficulty:
            raise ValueError("resolved difficulty does not match check proposal")
        if len(self.resolved_check.dice) != self.resolved_check.pool_size:
            raise ValueError("dice count does not match resolved pool size")
        if any(die < 1 or die > 6 for die in self.resolved_check.dice):
            raise ValueError("checkpoint dice must all be canonical d6 values")
        expected_successes = sum(
            die >= self.resolved_check.difficulty for die in self.resolved_check.dice
        )
        if self.resolved_check.success_count != expected_successes:
            raise ValueError("success count does not match exact checkpoint dice")
        return self

"""Typed state mutations and crash-recovery contracts for Module 09."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator

from epos.application.actions.models import CheckProposal, ResolvedCheck
from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, LocationId, SessionId, TurnNumber
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


StateMutation = Annotated[
    SetWorldFlagMutation
    | SetPlayerLocationMutation
    | SetNPCLocationMutation
    | SetNPCIntentionsMutation
    | ReplaceNPCEmotionalStateMutation
    | ReplaceNPCRelationshipMutation
    | SetWorldPhaseMutation,
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
    fingerprint: str = Field(min_length=64, max_length=64)


class DiceCheckpoint(DomainModel):
    """Crash-recovery payload persisted immediately after a Python dice roll."""

    session_id: SessionId
    state_reference: StateReference
    proposal: CheckProposal
    resolved_check: ResolvedCheck
    player_decision: str

    @field_validator("player_decision")
    @classmethod
    def validate_player_decision(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("player_decision must not be empty")
        return normalized

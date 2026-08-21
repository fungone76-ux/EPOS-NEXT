"""Strict contracts for private NPC cognition and validated reaction proposals."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import Field, field_validator

from epos.application.actions.models import ResolvedCheck, ValidatedAction
from epos.application.intimacy.models import ConsentScope, ConsentStatus
from epos.application.memory import RankedMemory
from epos.domain.base import DomainModel
from epos.domain.bond import BondState
from epos.domain.character_definition import NPCCharacterDefinition
from epos.domain.ids import EntityId, LocationId, MemoryId
from epos.domain.intimacy import IntimacyState
from epos.domain.knowledge import KnowledgeState
from epos.domain.memory import MemoryEntryState
from epos.domain.outfit import OutfitState
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState
from epos.domain.semantic import SEMANTIC_TOKEN_PATTERN, SemanticToken

_TOKEN_PATTERN = re.compile(SEMANTIC_TOKEN_PATTERN)


def _normalize_token(value: str, *, field_name: str) -> str:
    normalized = value.strip().casefold()
    if not _TOKEN_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field_name} must be one semantic token")
    return normalized


class CognitionScene(DomainModel):
    """Only facts observable in the current local scene."""

    location_id: LocationId
    present_entity_ids: tuple[EntityId, ...] = ()
    observable_facts: tuple[str, ...] = ()
    summary: str = ""


class SecretCognitiveState(DomainModel):
    """A secret known privately by the NPC plus Python-derived disclosure permission."""

    secret_id: str
    fact: str
    disclosure_allowed: bool


class PrivateCognitiveContext(DomainModel):
    """Private NPC-only reasoning context; never a player-facing narration contract."""

    npc_id: EntityId
    npc_name: str
    role: str
    player_id: EntityId
    character_definition: NPCCharacterDefinition = Field(default_factory=NPCCharacterDefinition)
    personality: tuple[str, ...] = ()
    speech_style: str = ""
    desires: tuple[str, ...] = ()
    goals: tuple[str, ...] = ()
    fears: tuple[str, ...] = ()
    red_lines: tuple[str, ...] = ()
    current_intentions: tuple[str, ...] = ()
    emotional_state: EmotionalState
    relationship_with_player: RelationshipState
    bond_state: BondState
    intimacy_with_player: IntimacyState | None = None
    knowledge: KnowledgeState
    beliefs: KnowledgeState
    false_beliefs: KnowledgeState
    discoveries: KnowledgeState
    core_memories: tuple[MemoryEntryState, ...] = ()
    short_term_memories: tuple[MemoryEntryState, ...] = ()
    recalled_memories: tuple[RankedMemory, ...] = ()
    secrets: tuple[SecretCognitiveState, ...] = ()
    scene: CognitionScene
    player_input: str
    action: ValidatedAction
    resolved_check: ResolvedCheck | None = None
    current_outfit: OutfitState = OutfitState()
    available_outfit_ids: tuple[str, ...] = ()


class OutfitRequestDisposition(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COUNTEROFFER = "counteroffer"


class GeneratedOutfitItemProposal(DomainModel):
    """One bounded visual garment proposed by cognition for a missing outfit."""

    name: str = Field(min_length=1, max_length=80)
    slot: SemanticToken
    layer: int = Field(ge=0, le=100)
    coverage: tuple[SemanticToken, ...] = Field(default=(), max_length=12)
    material: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=80)

    @field_validator("name", "material", "color")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("generated outfit text must not be empty")
        return normalized

    @field_validator("slot")
    @classmethod
    def normalize_slot(cls, value: str) -> str:
        return _normalize_token(value, field_name="generated outfit slot")

    @field_validator("coverage")
    @classmethod
    def normalize_coverage(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                _normalize_token(value, field_name="generated outfit coverage")
                for value in values
            )
        )


class GeneratedOutfitProposal(DomainModel):
    """Creative outfit draft that becomes canonical only after Python validation."""

    name: str = Field(min_length=1, max_length=100)
    items: tuple[GeneratedOutfitItemProposal, ...] = Field(min_length=1, max_length=12)
    rationale: str = Field(default="", max_length=300)


class NPCReactionProposal(DomainModel):
    """Bounded semantic proposal from NPC reasoning; Python validates authority."""

    npc_id: EntityId
    speech: str = ""
    observable_behavior: tuple[str, ...] = ()
    semantic_intents: tuple[SemanticToken, ...] = ()
    referenced_memory_ids: tuple[MemoryId, ...] = ()
    referenced_secret_ids: tuple[str, ...] = ()
    proposed_outfit_id: str | None = None
    proposed_outfit: GeneratedOutfitProposal | None = None
    outfit_request_disposition: OutfitRequestDisposition | None = None
    consent_scope: ConsentScope | None = None
    consent_status: ConsentStatus | None = None
    consent_reason: str | None = None

    @field_validator("semantic_intents")
    @classmethod
    def normalize_semantic_intents(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                _normalize_token(value, field_name="semantic intent") for value in values
            )
        )

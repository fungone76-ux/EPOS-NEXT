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
        return tuple(dict.fromkeys(_normalize_token(value, field_name="generated outfit coverage") for value in values))


class GeneratedOutfitProposal(DomainModel):
    """Creative outfit draft that becomes canonical only after Python validation."""
    name: str = Field(min_length=1, max_length=100)
    tags: tuple[SemanticToken, ...] = Field(default=(), max_length=12)
    items: tuple[GeneratedOutfitItemProposal, ...] = Field(min_length=1, max_length=12)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(_normalize_token(value, field_name="generated outfit tag") for value in values))


class NPCOutfitRequestResponse(DomainModel):
    """NPC decision about a player request; it is not a state mutation."""
    disposition: OutfitRequestDisposition
    selected_outfit_id: str | None = None
    generated_outfit: GeneratedOutfitProposal | None = None


class NPCOutfitAction(DomainModel):
    """Structured in-scene outfit action proposed by the NPC."""
    requested_state: str
    outfit_id: str | None = None
    item_ids: tuple[str, ...] = ()

    @field_validator("requested_state")
    @classmethod
    def normalize_requested_state(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized not in {"wear_outfit", "remove_items", "rewear_items"}:
            raise ValueError("unsupported NPC outfit action")
        return normalized


class NPCIntimacyResponse(DomainModel):
    """The NPC's explicit scoped answer; Python binds actors and turn later."""
    scope: ConsentScope
    status: ConsentStatus


class NPCReactionProposal(DomainModel):
    """Token-only semantic LLM proposal; it has no player-facing prose channel."""
    npc_id: EntityId
    intent: SemanticToken
    speech_act: SemanticToken
    topic_tags: tuple[SemanticToken, ...] = ()
    emotional_tone: tuple[SemanticToken, ...] = ()
    action_intent: SemanticToken | None = None
    target_ids: tuple[EntityId, ...] = ()
    referenced_memory_ids: tuple[MemoryId, ...] = ()
    requested_secret_disclosures: tuple[str, ...] = ()
    outfit_request_response: NPCOutfitRequestResponse | None = None
    autonomous_outfit_action: NPCOutfitAction | None = None
    intimacy_response: NPCIntimacyResponse | None = None

    @field_validator("intent", "speech_act")
    @classmethod
    def semantic_token(cls, value: str) -> str:
        return _normalize_token(value, field_name="reaction token")

    @field_validator("action_intent")
    @classmethod
    def optional_semantic_token(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_token(value, field_name="action_intent")

    @field_validator("topic_tags", "emotional_tone")
    @classmethod
    def semantic_token_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_normalize_token(value, field_name="reaction tag") for value in values)


class ValidatedNPCReaction(DomainModel):
    """Python-authorized semantic reaction for later narration/mutation stages."""
    npc_id: EntityId
    intent: str
    speech_act: str
    topic_tags: tuple[str, ...] = ()
    emotional_tone: tuple[str, ...] = ()
    action_intent: str | None = None
    target_ids: tuple[EntityId, ...] = ()
    referenced_memory_ids: tuple[MemoryId, ...] = ()
    authorized_secret_disclosures: tuple[str, ...] = ()
    outfit_request_response: NPCOutfitRequestResponse | None = None
    autonomous_outfit_action: NPCOutfitAction | None = None
    intimacy_response: NPCIntimacyResponse | None = None


class CognitionResult(DomainModel):
    """Safe result leaving cognition; private context itself is deliberately not exposed."""
    reaction: ValidatedNPCReaction
    recalled_memory_ids: tuple[MemoryId, ...] = ()

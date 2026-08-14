"""Strict contracts for private NPC cognition and validated reaction proposals."""

from __future__ import annotations

import re

from pydantic import field_validator

from epos.application.actions.models import ResolvedCheck, ValidatedAction
from epos.application.memory import RankedMemory
from epos.domain.base import DomainModel
from epos.domain.bond import BondState
from epos.domain.ids import EntityId, LocationId, MemoryId
from epos.domain.intimacy import IntimacyState
from epos.domain.knowledge import KnowledgeState
from epos.domain.memory import MemoryEntryState
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState

_TOKEN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.:-]*$")


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


class NPCReactionProposal(DomainModel):
    """Token-only semantic LLM proposal; it has no player-facing prose channel."""

    npc_id: EntityId
    intent: str
    speech_act: str
    topic_tags: tuple[str, ...] = ()
    emotional_tone: tuple[str, ...] = ()
    action_intent: str | None = None
    target_ids: tuple[EntityId, ...] = ()
    referenced_memory_ids: tuple[MemoryId, ...] = ()
    requested_secret_disclosures: tuple[str, ...] = ()

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


class CognitionResult(DomainModel):
    """Safe result leaving cognition; private context itself is deliberately not exposed."""

    reaction: ValidatedNPCReaction
    recalled_memory_ids: tuple[MemoryId, ...] = ()

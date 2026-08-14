"""Strict contracts for private NPC cognition and validated reaction proposals."""

from __future__ import annotations

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
    """Untrusted semantic LLM proposal; no dialogue, state mutation, or player control."""

    npc_id: EntityId
    intent: str
    communication_goal: str
    emotional_tone: tuple[str, ...] = ()
    observable_action: str | None = None
    target_ids: tuple[EntityId, ...] = ()
    referenced_memory_ids: tuple[MemoryId, ...] = ()
    requested_secret_disclosures: tuple[str, ...] = ()

    @field_validator("intent", "communication_goal")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("cognition text fields must not be empty")
        return normalized


class ValidatedNPCReaction(DomainModel):
    """Python-authorized semantic reaction for later narration/mutation stages."""

    npc_id: EntityId
    intent: str
    communication_goal: str
    emotional_tone: tuple[str, ...] = ()
    observable_action: str | None = None
    target_ids: tuple[EntityId, ...] = ()
    referenced_memory_ids: tuple[MemoryId, ...] = ()
    authorized_secret_disclosures: tuple[str, ...] = ()


class CognitionResult(DomainModel):
    """Safe result leaving cognition; private context itself is deliberately not exposed."""

    reaction: ValidatedNPCReaction
    recalled_memory_ids: tuple[MemoryId, ...] = ()

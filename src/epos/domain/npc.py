"""Persistent NPC state. No LLM behavior lives in these entities."""

from pydantic import Field

from epos.domain.base import DomainModel
from epos.domain.bond import BondState
from epos.domain.ids import EntityId, LocationId, TurnNumber
from epos.domain.intimacy import IntimacyState
from epos.domain.knowledge import KnowledgeState
from epos.domain.memory import EmotionalMemoryState, MemoryEntryState
from epos.domain.outfit import OutfitState
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState
from epos.domain.visual_state import VisualState


class NPCIdentity(DomainModel):
    entity_id: EntityId
    name: str
    role: str
    background: str = ""


class SecretState(DomainModel):
    secret_id: str
    fact: str


class DisclosureRule(DomainModel):
    secret_id: str
    required_flags: tuple[str, ...] = ()


class NPCState(DomainModel):
    identity: NPCIdentity
    location_id: LocationId
    adult_verified: bool = False
    personality: tuple[str, ...] = ()
    speech_style: str = ""
    desires: tuple[str, ...] = ()
    fears: tuple[str, ...] = ()
    goals: tuple[str, ...] = ()
    secrets: tuple[SecretState, ...] = ()
    disclosure_rules: tuple[DisclosureRule, ...] = ()
    red_lines: tuple[str, ...] = ()
    stats: dict[str, float] = Field(default_factory=dict)
    knowledge: KnowledgeState = Field(default_factory=KnowledgeState)
    beliefs: KnowledgeState = Field(default_factory=KnowledgeState)
    false_beliefs: KnowledgeState = Field(default_factory=KnowledgeState)
    discoveries: KnowledgeState = Field(default_factory=KnowledgeState)
    outfit: OutfitState = Field(default_factory=OutfitState)
    visual_state: VisualState = Field(default_factory=VisualState)
    short_term_memory: tuple[MemoryEntryState, ...] = ()
    core_memories: tuple[MemoryEntryState, ...] = ()
    emotional_memory: tuple[EmotionalMemoryState, ...] = ()
    emotional_state: EmotionalState = Field(default_factory=EmotionalState)
    relationships: dict[EntityId, RelationshipState] = Field(default_factory=dict)
    intimacy: dict[EntityId, IntimacyState] = Field(default_factory=dict)
    bond_state: BondState = Field(default_factory=BondState)
    intentions: tuple[str, ...] = ()
    last_player_action: str | None = None
    last_action_turn: TurnNumber | None = None

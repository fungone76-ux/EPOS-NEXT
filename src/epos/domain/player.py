"""Authoritative player state. The player remains fully player-controlled."""

from pydantic import Field

from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, LocationId
from epos.domain.knowledge import KnowledgeState
from epos.domain.outfit import OutfitState
from epos.domain.relationships import RelationshipState
from epos.domain.visual_state import VisualState


class PlayerState(DomainModel):
    entity_id: EntityId
    name: str
    location_id: LocationId
    stats: dict[str, float] = Field(default_factory=dict)
    inventory: tuple[str, ...] = ()
    outfit: OutfitState = Field(default_factory=OutfitState)
    conditions: tuple[str, ...] = ()
    knowledge: KnowledgeState = Field(default_factory=KnowledgeState)
    relationships: dict[EntityId, RelationshipState] = Field(default_factory=dict)
    visual_state: VisualState = Field(default_factory=VisualState)

"""Strict Worldpack schemas kept separate from authoritative runtime state."""

from pydantic import Field, JsonValue

from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, EventId, LocationId, MissionId, SkillId, WorldpackId
from epos.domain.knowledge import KnowledgeState
from epos.domain.npc import DisclosureRule, SecretState
from epos.domain.outfit import OutfitItem
from epos.domain.world_state import LocationState, SkillDefinition, WorldState


class WorldpackPlayerDefinition(DomainModel):
    entity_id: EntityId
    name: str
    location_id: LocationId
    adult_verified: bool = False
    stats: dict[str, float] = Field(default_factory=dict)
    inventory: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    knowledge: KnowledgeState = Field(default_factory=KnowledgeState)
    starting_outfit_id: str | None = None


class WorldDocument(DomainModel):
    worldpack_id: WorldpackId
    title: str
    initial_day: int = Field(default=1, ge=1)
    initial_phase: str
    player: WorldpackPlayerDefinition
    world_truth: KnowledgeState = Field(default_factory=KnowledgeState)
    narrative_config: dict[str, JsonValue] = Field(default_factory=dict)
    rendering_config: dict[str, JsonValue] = Field(default_factory=dict)


class LocationsDocument(DomainModel):
    locations: tuple[LocationState, ...] = ()


class NPCDefinition(DomainModel):
    entity_id: EntityId
    name: str
    role: str
    background: str = ""
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
    starting_outfit_id: str | None = None


class NPCsDocument(DomainModel):
    npcs: tuple[NPCDefinition, ...] = ()


class SkillsDocument(DomainModel):
    skills: tuple[SkillDefinition, ...] = ()


class MissionDefinition(DomainModel):
    mission_id: MissionId
    status: str
    npc_ids: tuple[EntityId, ...] = ()
    location_ids: tuple[LocationId, ...] = ()
    required_skill_ids: tuple[SkillId, ...] = ()


class MissionsDocument(DomainModel):
    missions: tuple[MissionDefinition, ...] = ()


class EventDefinition(DomainModel):
    event_id: EventId
    status: str
    npc_ids: tuple[EntityId, ...] = ()
    location_id: LocationId | None = None
    mission_id: MissionId | None = None


class EventsDocument(DomainModel):
    events: tuple[EventDefinition, ...] = ()


class OutfitDefinition(DomainModel):
    outfit_id: str
    owner_id: EntityId
    items: tuple[OutfitItem, ...] = ()


class WardrobesDocument(DomainModel):
    outfits: tuple[OutfitDefinition, ...] = ()


class CharacterVisualCanon(DomainModel):
    entity_id: EntityId
    base_prompt: str
    role_prompt: str = ""
    negative_prompt: str = ""
    lora_alias: str | None = None
    visual_gender: str
    canonical_traits: tuple[str, ...] = ()


class VisualDocument(DomainModel):
    loras: dict[str, str] = Field(default_factory=dict)
    characters: tuple[CharacterVisualCanon, ...] = ()
    world_positive: tuple[str, ...] = ()
    world_negative: tuple[str, ...] = ()


class ScheduleEntryDefinition(DomainModel):
    phase: str
    location_id: LocationId


class NPCScheduleDefinition(DomainModel):
    npc_id: EntityId
    entries: tuple[ScheduleEntryDefinition, ...] = ()


class SchedulesDocument(DomainModel):
    schedules: tuple[NPCScheduleDefinition, ...] = ()


class SemanticLibraryEntry(DomainModel):
    entry_id: str
    description: str = ""
    tags: tuple[str, ...] = ()


class SemanticLibraryDocument(DomainModel):
    entries: tuple[SemanticLibraryEntry, ...] = ()


class WorldpackBundle(DomainModel):
    world: WorldDocument
    locations: LocationsDocument
    npcs: NPCsDocument
    skills: SkillsDocument
    missions: MissionsDocument = Field(default_factory=MissionsDocument)
    events: EventsDocument = Field(default_factory=EventsDocument)
    wardrobes: WardrobesDocument = Field(default_factory=WardrobesDocument)
    visual: VisualDocument = Field(default_factory=VisualDocument)
    schedules: SchedulesDocument = Field(default_factory=SchedulesDocument)
    action_library: SemanticLibraryDocument = Field(default_factory=SemanticLibraryDocument)
    pose_library: SemanticLibraryDocument = Field(default_factory=SemanticLibraryDocument)
    camera_library: SemanticLibraryDocument = Field(default_factory=SemanticLibraryDocument)
    outfit_library: SemanticLibraryDocument = Field(default_factory=SemanticLibraryDocument)


class LoadedWorldpack(DomainModel):
    world_state: WorldState
    visual: VisualDocument
    schedules: SchedulesDocument
    action_library: SemanticLibraryDocument
    pose_library: SemanticLibraryDocument
    camera_library: SemanticLibraryDocument
    outfit_library: SemanticLibraryDocument

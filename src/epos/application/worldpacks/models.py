"""Strict Worldpack schemas kept separate from authoritative runtime state."""

from typing import Literal

from pydantic import Field, JsonValue, field_validator

from epos.domain.base import DomainModel
from epos.domain.character_definition import NPCCharacterDefinition
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
    character_definition: NPCCharacterDefinition = Field(default_factory=NPCCharacterDefinition)
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
    tags: tuple[str, ...] = ()
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
    characters: dict[EntityId, CharacterVisualCanon] = Field(default_factory=dict)
    world_positive: tuple[str, ...] = ()
    world_negative: tuple[str, ...] = ()

    @field_validator("characters", mode="before")
    @classmethod
    def index_characters(cls, value: object) -> object:
        """Accept ergonomic YAML lists but normalize to canonical entity-id lookup."""
        if value is None:
            return {}
        if isinstance(value, list):
            indexed: dict[str, object] = {}
            for item in value:
                if not isinstance(item, dict):
                    return value
                entity_id = item.get("entity_id")
                if not isinstance(entity_id, str):
                    return value
                if entity_id in indexed:
                    raise ValueError(f"duplicate visual character: {entity_id}")
                indexed[entity_id] = item
            return indexed
        if isinstance(value, dict):
            normalized: dict[str, object] = {}
            for key, item in value.items():
                if not isinstance(key, str) or not isinstance(item, dict):
                    return value
                definition = dict(item)
                definition.setdefault("entity_id", key)
                normalized[key] = definition
            return normalized
        return value


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
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    positive_fragment: str = ""

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, aliases: tuple[str, ...]) -> tuple[str, ...]:
        seen: set[str] = set()
        for alias in aliases:
            key = " ".join(alias.strip().casefold().split())
            if not key:
                raise ValueError("semantic library alias must not be empty")
            if key in seen:
                raise ValueError(f"duplicate semantic library alias: {alias}")
            seen.add(key)
        return aliases


class SemanticLibraryDocument(DomainModel):
    schema_version: Literal[1] = 1
    library_id: str | None = None
    description: str = ""
    world_id: WorldpackId | None = None
    entries: tuple[SemanticLibraryEntry, ...] = ()

    @field_validator("library_id")
    @classmethod
    def validate_library_id(cls, library_id: str | None) -> str | None:
        if library_id is None:
            return None
        normalized = library_id.strip()
        if not normalized:
            raise ValueError("semantic library id must not be empty")
        return normalized

    @field_validator("entries")
    @classmethod
    def validate_unique_entry_ids_and_aliases(
        cls,
        entries: tuple[SemanticLibraryEntry, ...],
    ) -> tuple[SemanticLibraryEntry, ...]:
        seen_ids: set[str] = set()
        alias_owners: dict[str, str] = {}
        for entry in entries:
            entry_key = entry.entry_id.strip().casefold()
            if not entry_key:
                raise ValueError("semantic library entry id must not be empty")
            if entry_key in seen_ids:
                raise ValueError(f"duplicate semantic library entry: {entry.entry_id}")
            seen_ids.add(entry_key)
            for alias in entry.aliases:
                alias_key = " ".join(alias.strip().casefold().split())
                owner = alias_owners.get(alias_key)
                if owner is not None and owner != entry_key:
                    raise ValueError(
                        "duplicate semantic library alias across entries: "
                        f"{alias} ({owner}, {entry.entry_id})"
                    )
                alias_owners[alias_key] = entry_key
        return entries


class AdultSemanticLibraryDocument(SemanticLibraryDocument):
    """Validated adult visual vocabulary kept outside the standard visual pipeline."""

    content_rating: Literal["adult_18_plus"]


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
    lighting_library: SemanticLibraryDocument = Field(default_factory=SemanticLibraryDocument)
    location_visual_library: SemanticLibraryDocument = Field(
        default_factory=SemanticLibraryDocument
    )
    style_library: SemanticLibraryDocument = Field(default_factory=SemanticLibraryDocument)
    sex_library: AdultSemanticLibraryDocument | None = None


class LoadedWorldpack(DomainModel):
    world_state: WorldState
    visual: VisualDocument
    schedules: SchedulesDocument
    action_library: SemanticLibraryDocument
    pose_library: SemanticLibraryDocument
    camera_library: SemanticLibraryDocument
    outfit_library: SemanticLibraryDocument
    lighting_library: SemanticLibraryDocument = Field(default_factory=SemanticLibraryDocument)
    location_visual_library: SemanticLibraryDocument = Field(
        default_factory=SemanticLibraryDocument
    )
    style_library: SemanticLibraryDocument = Field(default_factory=SemanticLibraryDocument)
    sex_library: AdultSemanticLibraryDocument | None = None

"""Authoritative root state for everything that is true in one EPOS session."""

from pydantic import Field, JsonValue

from epos.domain.base import DomainModel
from epos.domain.ids import (
    EntityId,
    EventId,
    LocationId,
    MissionId,
    SessionId,
    SkillId,
    TurnNumber,
    WorldpackId,
)
from epos.domain.knowledge import KnowledgeState
from epos.domain.npc import NPCState
from epos.domain.player import PlayerState


class LocationState(DomainModel):
    location_id: LocationId
    name: str


class MissionState(DomainModel):
    mission_id: MissionId
    status: str


class EventState(DomainModel):
    event_id: EventId
    status: str


class NarrativeThreadState(DomainModel):
    thread_id: str
    status: str


class SkillDefinition(DomainModel):
    skill_id: SkillId
    name: str
    description: str = ""
    check_intents: tuple[str, ...] = ()


class RenderingConfig(DomainModel):
    settings: dict[str, JsonValue] = Field(default_factory=dict)


class NarrativeConfig(DomainModel):
    settings: dict[str, JsonValue] = Field(default_factory=dict)


class WorldState(DomainModel):
    session_id: SessionId
    worldpack_id: WorldpackId
    turn_number: TurnNumber
    day: int = Field(ge=1)
    world_phase: str
    player: PlayerState
    npcs: dict[EntityId, NPCState] = Field(default_factory=dict)
    locations: dict[LocationId, LocationState] = Field(default_factory=dict)
    missions: dict[MissionId, MissionState] = Field(default_factory=dict)
    events: dict[EventId, EventState] = Field(default_factory=dict)
    flags: dict[str, bool] = Field(default_factory=dict)
    threads: dict[str, NarrativeThreadState] = Field(default_factory=dict)
    skill_definitions: dict[SkillId, SkillDefinition] = Field(default_factory=dict)
    world_truth: KnowledgeState = Field(default_factory=KnowledgeState)
    rendering_config: RenderingConfig = Field(default_factory=RenderingConfig)
    narrative_config: NarrativeConfig = Field(default_factory=NarrativeConfig)

    def get_npc(self, npc_id: EntityId) -> NPCState:
        """Return one NPC by canonical id."""

        return self.npcs[npc_id]

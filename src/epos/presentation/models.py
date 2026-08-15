"""Shared presentation contracts consumed by desktop and HTTP adapters."""

from __future__ import annotations

from pydantic import Field, JsonValue

from epos.application.diagnostics import RuntimeHealthView
from epos.application.results import TurnDialogueLine, TurnVisualResult
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
from epos.domain.world_state import WorldState


class PresentNPCView(DomainModel):
    entity_id: EntityId
    name: str
    role: str


class MissionView(DomainModel):
    mission_id: MissionId
    status: str


class EventView(DomainModel):
    event_id: EventId
    status: str


class PlayerSkillView(DomainModel):
    skill_id: SkillId
    name: str
    rating: float | None = None


class SessionView(DomainModel):
    session_id: SessionId
    turn_number: TurnNumber
    worldpack_id: WorldpackId
    location_id: LocationId
    location_name: str
    day: int = Field(ge=1)
    world_phase: str
    present_npcs: tuple[PresentNPCView, ...] = ()
    missions: tuple[MissionView, ...] = ()
    events: tuple[EventView, ...] = ()
    player_skills: tuple[PlayerSkillView, ...] = ()
    known_world_info: dict[str, JsonValue] = Field(default_factory=dict)

    @classmethod
    def from_world_state(cls, state: WorldState) -> SessionView:
        location = state.locations[state.player.location_id]
        return cls(
            session_id=state.session_id,
            turn_number=state.turn_number,
            worldpack_id=state.worldpack_id,
            location_id=location.location_id,
            location_name=location.name,
            day=state.day,
            world_phase=state.world_phase,
            present_npcs=tuple(
                PresentNPCView(
                    entity_id=npc_id,
                    name=npc.identity.name,
                    role=npc.identity.role,
                )
                for npc_id, npc in sorted(state.npcs.items(), key=lambda item: str(item[0]))
                if npc.location_id == state.player.location_id
            ),
            missions=tuple(
                MissionView(mission_id=mission_id, status=mission.status)
                for mission_id, mission in sorted(
                    state.missions.items(), key=lambda item: str(item[0])
                )
            ),
            events=tuple(
                EventView(event_id=event_id, status=event.status)
                for event_id, event in sorted(
                    state.events.items(), key=lambda item: str(item[0])
                )
            ),
            player_skills=tuple(
                PlayerSkillView(
                    skill_id=skill_id,
                    name=skill.name,
                    rating=state.player.stats.get(str(skill_id)),
                )
                for skill_id, skill in sorted(
                    state.skill_definitions.items(), key=lambda item: str(item[0])
                )
            ),
            known_world_info=dict(state.player.knowledge.facts),
        )


class WorldpackView(DomainModel):
    worldpack_id: WorldpackId
    title: str


class StoryPanelState(DomainModel):
    narration: str = ""
    dialogues: tuple[TurnDialogueLine, ...] = ()


class VisualPanelState(DomainModel):
    current_image: str | None = None
    result: TurnVisualResult | None = None
    show_debug: bool = False


class DesktopViewState(DomainModel):
    session: SessionView
    story: StoryPanelState = Field(default_factory=StoryPanelState)
    visual: VisualPanelState = Field(default_factory=VisualPanelState)
    health: RuntimeHealthView

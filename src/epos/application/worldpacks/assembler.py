"""Validate Worldpack references and build authoritative runtime state."""

from collections.abc import Iterable

from epos.application.worldpacks.models import (
    LoadedWorldpack,
    NPCDefinition,
    OutfitDefinition,
    SemanticLibraryDocument,
    WorldpackBundle,
)
from epos.domain.errors import EposValidationError
from epos.domain.ids import EntityId, LocationId, MissionId, SessionId, SkillId, TurnNumber
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.outfit import OutfitState
from epos.domain.player import PlayerState
from epos.domain.world_state import (
    EventState,
    MissionState,
    NarrativeConfig,
    RenderingConfig,
    WorldState,
)


class WorldpackValidationError(EposValidationError):
    def __init__(self, message: str, *, code: str = "worldpack.reference.invalid") -> None:
        super().__init__(message, code=code)


class WorldpackAssembler:
    """Python-authoritative cross-reference validation and WorldState construction."""

    def build(self, bundle: WorldpackBundle, *, session_id: str) -> LoadedWorldpack:
        locations = {location.location_id: location for location in bundle.locations.locations}
        npcs = {npc.entity_id: npc for npc in bundle.npcs.npcs}
        skills = {skill.skill_id: skill for skill in bundle.skills.skills}
        missions = {mission.mission_id: mission for mission in bundle.missions.missions}
        events = {event.event_id: event for event in bundle.events.events}
        outfits = {outfit.outfit_id: outfit for outfit in bundle.wardrobes.outfits}

        self._require_unique("location", bundle.locations.locations, len(locations))
        self._require_unique("NPC", bundle.npcs.npcs, len(npcs))
        self._require_unique("skill", bundle.skills.skills, len(skills))
        self._require_unique("mission", bundle.missions.missions, len(missions))
        self._require_unique("event", bundle.events.events, len(events))
        self._require_unique("outfit", bundle.wardrobes.outfits, len(outfits))

        location_ids = set(locations)
        npc_ids = set(npcs)
        skill_ids = set(skills)
        mission_ids = set(missions)
        actor_ids = {bundle.world.player.entity_id, *npc_ids}
        self._validate_player(bundle, location_ids, outfits)
        self._validate_npcs(bundle, location_ids, outfits)
        self._validate_outfit_owners(bundle, actor_ids)
        self._validate_missions(bundle, npc_ids, location_ids, skill_ids)
        self._validate_events(bundle, npc_ids, location_ids, mission_ids)
        self._validate_visual(bundle, actor_ids)
        self._validate_schedules(bundle, npc_ids, location_ids)
        self._validate_semantic_libraries(bundle)

        player = self._build_player(bundle, outfits)
        runtime_npcs = {
            npc_id: self._build_npc(definition, outfits) for npc_id, definition in npcs.items()
        }
        world_state = WorldState(
            session_id=SessionId(session_id),
            worldpack_id=bundle.world.worldpack_id,
            turn_number=TurnNumber(0),
            day=bundle.world.initial_day,
            world_phase=bundle.world.initial_phase,
            player=player,
            npcs=runtime_npcs,
            locations=locations,
            missions={
                mission_id: MissionState(mission_id=mission_id, status=definition.status)
                for mission_id, definition in missions.items()
            },
            events={
                event_id: EventState(event_id=event_id, status=definition.status)
                for event_id, definition in events.items()
            },
            skill_definitions=skills,
            world_truth=bundle.world.world_truth,
            rendering_config=RenderingConfig(settings=bundle.world.rendering_config),
            narrative_config=NarrativeConfig(settings=bundle.world.narrative_config),
        )
        visual = bundle.visual.model_copy(deep=True)
        visual.characters = {
            entity_id: visual.characters[entity_id]
            for entity_id in sorted(visual.characters, key=str)
        }
        return LoadedWorldpack(
            world_state=world_state,
            visual=visual,
            schedules=bundle.schedules,
            action_library=bundle.action_library,
            pose_library=bundle.pose_library,
            camera_library=bundle.camera_library,
            outfit_library=bundle.outfit_library,
            lighting_library=bundle.lighting_library,
            location_visual_library=bundle.location_visual_library,
            style_library=bundle.style_library,
        )

    @staticmethod
    def _require_unique(kind: str, items: Iterable[object], indexed_count: int) -> None:
        if len(tuple(items)) != indexed_count:
            raise WorldpackValidationError(f"duplicate {kind} id")

    @staticmethod
    def _validate_player(
        bundle: WorldpackBundle,
        location_ids: set[LocationId],
        outfits: dict[str, OutfitDefinition],
    ) -> None:
        player = bundle.world.player
        if player.location_id not in location_ids:
            raise WorldpackValidationError(f"unknown location: {player.location_id}")
        if player.starting_outfit_id is not None:
            outfit = outfits.get(player.starting_outfit_id)
            if outfit is None or outfit.owner_id != player.entity_id:
                raise WorldpackValidationError(f"invalid outfit: {player.starting_outfit_id}")

    @staticmethod
    def _validate_npcs(
        bundle: WorldpackBundle,
        location_ids: set[LocationId],
        outfits: dict[str, OutfitDefinition],
    ) -> None:
        for npc in bundle.npcs.npcs:
            if npc.location_id not in location_ids:
                raise WorldpackValidationError(f"unknown location: {npc.location_id}")
            if npc.starting_outfit_id is not None:
                outfit = outfits.get(npc.starting_outfit_id)
                if outfit is None or outfit.owner_id != npc.entity_id:
                    raise WorldpackValidationError(f"invalid outfit: {npc.starting_outfit_id}")

    @staticmethod
    def _validate_outfit_owners(bundle: WorldpackBundle, actor_ids: set[EntityId]) -> None:
        for outfit in bundle.wardrobes.outfits:
            if outfit.owner_id not in actor_ids:
                raise WorldpackValidationError(f"unknown NPC or player: {outfit.owner_id}")
            item_ids = {item.item_id for item in outfit.items}
            if len(item_ids) != len(outfit.items):
                raise WorldpackValidationError(f"invalid outfit: {outfit.outfit_id}")

    @staticmethod
    def _validate_missions(
        bundle: WorldpackBundle,
        npc_ids: set[EntityId],
        location_ids: set[LocationId],
        skill_ids: set[SkillId],
    ) -> None:
        for mission in bundle.missions.missions:
            for npc_id in mission.npc_ids:
                if npc_id not in npc_ids:
                    raise WorldpackValidationError(f"unknown NPC: {npc_id}")
            for location_id in mission.location_ids:
                if location_id not in location_ids:
                    raise WorldpackValidationError(f"unknown location: {location_id}")
            for skill_id in mission.required_skill_ids:
                if skill_id not in skill_ids:
                    raise WorldpackValidationError(f"unknown skill: {skill_id}")

    @staticmethod
    def _validate_events(
        bundle: WorldpackBundle,
        npc_ids: set[EntityId],
        location_ids: set[LocationId],
        mission_ids: set[MissionId],
    ) -> None:
        for event in bundle.events.events:
            for npc_id in event.npc_ids:
                if npc_id not in npc_ids:
                    raise WorldpackValidationError(f"unknown NPC: {npc_id}")
            if event.location_id is not None and event.location_id not in location_ids:
                raise WorldpackValidationError(f"unknown location: {event.location_id}")
            if event.mission_id is not None and event.mission_id not in mission_ids:
                raise WorldpackValidationError(f"invalid mission reference: {event.mission_id}")

    @staticmethod
    def _validate_visual(bundle: WorldpackBundle, actor_ids: set[EntityId]) -> None:
        for entity_id, character in bundle.visual.characters.items():
            if entity_id != character.entity_id:
                raise WorldpackValidationError(f"visual character id mismatch: {entity_id}")
            if character.entity_id not in actor_ids:
                raise WorldpackValidationError(f"unknown NPC or player: {character.entity_id}")
            alias = character.lora_alias
            if alias is not None and alias not in bundle.visual.loras:
                raise WorldpackValidationError(f"unknown LoRA alias: {alias}")

    @staticmethod
    def _validate_schedules(
        bundle: WorldpackBundle,
        npc_ids: set[EntityId],
        location_ids: set[LocationId],
    ) -> None:
        scheduled: set[EntityId] = set()
        for schedule in bundle.schedules.schedules:
            if schedule.npc_id not in npc_ids:
                raise WorldpackValidationError(f"unknown NPC: {schedule.npc_id}")
            if schedule.npc_id in scheduled:
                raise WorldpackValidationError(f"duplicate schedule: {schedule.npc_id}")
            scheduled.add(schedule.npc_id)
            for entry in schedule.entries:
                if entry.location_id not in location_ids:
                    raise WorldpackValidationError(f"unknown location: {entry.location_id}")

    @classmethod
    def _validate_semantic_libraries(cls, bundle: WorldpackBundle) -> None:
        libraries: tuple[tuple[str, SemanticLibraryDocument], ...] = (
            ("action_library", bundle.action_library),
            ("pose_library", bundle.pose_library),
            ("camera_library", bundle.camera_library),
            ("outfit_library", bundle.outfit_library),
            ("lighting_library", bundle.lighting_library),
            ("location_visual_library", bundle.location_visual_library),
            ("style_library", bundle.style_library),
        )
        for expected_id, library in libraries:
            if library.library_id is not None and library.library_id != expected_id:
                raise WorldpackValidationError(
                    f"semantic library id mismatch: {library.library_id} != {expected_id}"
                )
            if library.world_id is not None and library.world_id != bundle.world.worldpack_id:
                raise WorldpackValidationError(
                    "semantic library world_id mismatch: "
                    f"{library.world_id} != {bundle.world.worldpack_id}"
                )

    @staticmethod
    def _resolve_outfit(
        actor_id: EntityId,
        outfit_id: str | None,
        outfits: dict[str, OutfitDefinition],
    ) -> OutfitState:
        if outfit_id is None:
            return OutfitState()
        outfit = outfits[outfit_id]
        if outfit.owner_id != actor_id:
            raise WorldpackValidationError(f"invalid outfit: {outfit_id}")
        return OutfitState(items=outfit.items)

    def _build_player(
        self,
        bundle: WorldpackBundle,
        outfits: dict[str, OutfitDefinition],
    ) -> PlayerState:
        definition = bundle.world.player
        return PlayerState(
            entity_id=definition.entity_id,
            name=definition.name,
            location_id=definition.location_id,
            adult_verified=definition.adult_verified,
            stats=definition.stats,
            inventory=definition.inventory,
            outfit=self._resolve_outfit(
                definition.entity_id, definition.starting_outfit_id, outfits
            ),
            conditions=definition.conditions,
            knowledge=definition.knowledge,
        )

    def _build_npc(
        self,
        definition: NPCDefinition,
        outfits: dict[str, OutfitDefinition],
    ) -> NPCState:
        return NPCState(
            identity=NPCIdentity(
                entity_id=definition.entity_id,
                name=definition.name,
                role=definition.role,
                background=definition.background,
            ),
            location_id=definition.location_id,
            adult_verified=definition.adult_verified,
            personality=definition.personality,
            speech_style=definition.speech_style,
            desires=definition.desires,
            fears=definition.fears,
            goals=definition.goals,
            secrets=definition.secrets,
            disclosure_rules=definition.disclosure_rules,
            red_lines=definition.red_lines,
            stats=definition.stats,
            knowledge=definition.knowledge,
            beliefs=definition.beliefs,
            false_beliefs=definition.false_beliefs,
            discoveries=definition.discoveries,
            outfit=self._resolve_outfit(
                definition.entity_id, definition.starting_outfit_id, outfits
            ),
        )

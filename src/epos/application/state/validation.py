"""Python-owned authority and complete-world validation for state commits."""

from __future__ import annotations

from epos.application.state.errors import MutationAuthorityError, StateMutationError
from epos.application.state.models import MutationBatch
from epos.domain.world_state import WorldState


class MutationAuthorityValidator:
    @staticmethod
    def validate(batch: MutationBatch) -> None:
        for mutation in batch.mutations:
            if mutation.authority is not batch.producer:
                raise MutationAuthorityError(
                    "mutation authority mismatch: "
                    f"{mutation.kind} requires {mutation.authority}, "
                    f"producer was {batch.producer}"
                )


class WorldStateCommitValidator:
    """Revalidate the entire root model plus cross-reference invariants."""

    @staticmethod
    def validate(candidate: WorldState) -> WorldState:
        validated = WorldState.model_validate(candidate.model_dump(mode="python"))

        if validated.player.location_id not in validated.locations:
            raise StateMutationError(
                f"player location {validated.player.location_id} does not exist"
            )

        for npc_id, npc in validated.npcs.items():
            if npc.identity.entity_id != npc_id:
                raise StateMutationError(
                    f"npc key {npc_id} does not match identity {npc.identity.entity_id}"
                )
            if npc.location_id not in validated.locations:
                raise StateMutationError(
                    f"npc {npc_id} location {npc.location_id} does not exist"
                )

        for location_id, location in validated.locations.items():
            if location.location_id != location_id:
                raise StateMutationError(
                    f"location key {location_id} does not match {location.location_id}"
                )

        for skill_id, skill in validated.skill_definitions.items():
            if skill.skill_id != skill_id:
                raise StateMutationError(
                    f"skill key {skill_id} does not match {skill.skill_id}"
                )

        actor_ids = {validated.player.entity_id, *validated.npcs}
        for outfit_id, outfit in validated.wardrobes.items():
            if outfit.outfit_id != outfit_id:
                raise StateMutationError(
                    f"wardrobe key {outfit_id} does not match {outfit.outfit_id}"
                )
            if outfit.owner_id not in actor_ids:
                raise StateMutationError(
                    f"wardrobe outfit {outfit_id} has unknown owner {outfit.owner_id}"
                )
            item_ids = tuple(item.item_id for item in outfit.items)
            if len(item_ids) != len(set(item_ids)):
                raise StateMutationError(f"wardrobe outfit {outfit_id} has duplicate items")

        for mission_id, mission in validated.missions.items():
            if mission.mission_id != mission_id:
                raise StateMutationError(
                    f"mission key {mission_id} does not match {mission.mission_id}"
                )

        for event_id, event in validated.events.items():
            if event.event_id != event_id:
                raise StateMutationError(
                    f"event key {event_id} does not match {event.event_id}"
                )

        return validated

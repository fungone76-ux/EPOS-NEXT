"""Strict contracts for semantic player actions and resolved checks."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator

from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, LocationId, SkillId
from epos.domain.world_state import SkillDefinition, WorldState


class CheckStakes(DomainModel):
    """Semantic stakes proposed by interpretation, never authoritative mutations."""

    on_success: tuple[str, ...] = ()
    on_failure: tuple[str, ...] = ()


class CheckProposal(DomainModel):
    """Untrusted LLM proposal that Python must validate before any roll."""

    skill_id: SkillId
    difficulty: int = Field(ge=1, le=6)
    stakes: CheckStakes | None = None


class MovementProposal(DomainModel):
    """Semantic movement request; no location mutation occurs here."""

    destination_id: LocationId


class OutfitRequestProposal(DomainModel):
    """Semantic request concerning an outfit; no outfit mutation occurs here."""

    target_id: EntityId
    item_id: str | None = None
    requested_state: str


class ActionInterpretation(DomainModel):
    """LLM-produced semantic interpretation with no authoritative outcome fields."""

    intent: str
    target_ids: tuple[EntityId, ...] = ()
    movement: MovementProposal | None = None
    check: CheckProposal | None = None
    outfit_request: OutfitRequestProposal | None = None

    @field_validator("intent")
    @classmethod
    def normalize_intent(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not normalized:
            raise ValueError("intent must not be empty")
        return normalized


class ActionInterpreterContext(DomainModel):
    """Minimal world-aware context exposed to the action interpreter LLM."""

    player_input: str
    player_id: EntityId
    location_id: LocationId
    present_npc_ids: tuple[EntityId, ...] = ()
    known_location_ids: tuple[LocationId, ...] = ()
    skill_catalog: tuple[SkillDefinition, ...] = ()
    player_skill_ratings: dict[SkillId, int] = Field(default_factory=dict)

    @classmethod
    def from_world_state(
        cls,
        state: WorldState,
        *,
        player_input: str,
        known_location_ids: tuple[LocationId, ...],
    ) -> ActionInterpreterContext:
        present_npcs = tuple(
            sorted(
                (
                    npc_id
                    for npc_id, npc in state.npcs.items()
                    if npc.location_id == state.player.location_id
                ),
                key=str,
            )
        )
        skills = tuple(sorted(state.skill_definitions.values(), key=lambda skill: str(skill.skill_id)))
        ratings: dict[SkillId, int] = {}
        for skill in skills:
            raw_rating = state.player.stats.get(str(skill.skill_id))
            if raw_rating is not None and raw_rating > 0 and raw_rating.is_integer():
                ratings[skill.skill_id] = int(raw_rating)
        return cls(
            player_input=player_input,
            player_id=state.player.entity_id,
            location_id=state.player.location_id,
            present_npc_ids=present_npcs,
            known_location_ids=known_location_ids,
            skill_catalog=skills,
            player_skill_ratings=ratings,
        )


class ValidatedAction(DomainModel):
    """Semantic action accepted by Python world/authorization validation."""

    intent: str
    target_ids: tuple[EntityId, ...] = ()
    movement: MovementProposal | None = None
    check: CheckProposal | None = None
    outfit_request: OutfitRequestProposal | None = None
    skill_rating: int | None = Field(default=None, ge=1)


class CheckOutcome(str, Enum):
    CRITICAL_FAILURE = "critical_failure"
    FAILURE = "failure"
    PARTIAL_SUCCESS = "partial_success"
    FULL_SUCCESS = "full_success"


class ResolvedCheck(DomainModel):
    """Canonical Python-owned dice result ready for later checkpointing/narration."""

    skill_id: SkillId
    difficulty: int = Field(ge=1, le=6)
    rating: int = Field(ge=1)
    pool_size: int = Field(ge=1)
    dice: tuple[int, ...]
    success_count: int = Field(ge=0)
    outcome: CheckOutcome

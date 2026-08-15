"""Strict contracts for semantic player actions and resolved checks."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, LocationId, SkillId
from epos.domain.outfit import OutfitState
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
    outfit_id: str | None = None
    item_ids: tuple[str, ...] = ()
    semantic_tags: tuple[str, ...] = ()

    @field_validator("requested_state")
    @classmethod
    def normalize_requested_state(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not normalized:
            raise ValueError("requested_state must not be empty")
        return normalized

    @field_validator("semantic_tags")
    @classmethod
    def normalize_semantic_tags(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value.strip().casefold() for value in values if value.strip()))


class OutfitOption(DomainModel):
    """Disclosure-safe canonical wardrobe option exposed to interpretation/cognition."""

    outfit_id: str
    owner_id: EntityId
    tags: tuple[str, ...] = ()


class ValidatedOutfitRequest(DomainModel):
    """Python-resolved request with canonical candidates or bounded generation permission."""

    target_id: EntityId
    requested_state: str
    item_ids: tuple[str, ...] = ()
    semantic_tags: tuple[str, ...] = ()
    candidate_outfit_ids: tuple[str, ...] = ()
    requested_concept: str | None = None
    allow_generated_outfit: bool = False


class ObservationIntent(DomainModel):
    """Player-controlled visual attention without changing authoritative world state."""

    subject_id: EntityId
    region: str

    @field_validator("region")
    @classmethod
    def normalize_region(cls, value: str) -> str:
        normalized = value.strip().casefold().replace(" ", "_")
        if not normalized or not all(part.isalnum() for part in normalized.split("_")):
            raise ValueError("observation region must be a stable semantic token")
        return normalized


class ActionInterpretation(DomainModel):
    """LLM-produced semantic interpretation with no authoritative outcome fields."""

    intent: str
    target_ids: tuple[EntityId, ...] = ()
    movement: MovementProposal | None = None
    check: CheckProposal | None = None
    outfit_request: OutfitRequestProposal | None = None
    observation: ObservationIntent | None = None

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
    wardrobe_options: tuple[OutfitOption, ...] = ()
    current_outfits: dict[EntityId, OutfitState] = Field(default_factory=dict)

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
        skills = tuple(
            sorted(
                state.skill_definitions.values(),
                key=lambda skill: str(skill.skill_id),
            )
        )
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
            wardrobe_options=tuple(
                OutfitOption(
                    outfit_id=outfit.outfit_id,
                    owner_id=outfit.owner_id,
                    tags=outfit.tags,
                )
                for outfit in sorted(state.wardrobes.values(), key=lambda item: item.outfit_id)
                if outfit.owner_id in {state.player.entity_id, *present_npcs}
            ),
            current_outfits={
                state.player.entity_id: state.player.outfit.model_copy(deep=True),
                **{
                    npc_id: state.npcs[npc_id].outfit.model_copy(deep=True)
                    for npc_id in present_npcs
                },
            },
        )


class ValidatedAction(DomainModel):
    """Semantic action accepted by Python world/authorization validation."""

    intent: str
    target_ids: tuple[EntityId, ...] = ()
    movement: MovementProposal | None = None
    check: CheckProposal | None = None
    outfit_request: ValidatedOutfitRequest | None = None
    observation: ObservationIntent | None = None
    skill_rating: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_observation_target(self) -> ValidatedAction:
        if self.observation is not None and self.observation.subject_id not in self.target_ids:
            raise ValueError("observation subject must also be an action target")
        return self


class CheckOutcome(StrEnum):
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

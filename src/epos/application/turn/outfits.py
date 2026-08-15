"""Python-authoritative outfit mutation planning after validated NPC decisions."""

from __future__ import annotations

import re

from epos.application.actions.models import ValidatedOutfitRequest
from epos.application.cognition.models import (
    CognitionResult,
    GeneratedOutfitProposal,
    NPCOutfitAction,
    OutfitRequestDisposition,
)
from epos.application.state import (
    MutationAuthority,
    MutationBatch,
    ReplaceNPCOutfitMutation,
    StateMutation,
    UpsertWardrobeOutfitMutation,
)
from epos.application.turn.errors import TurnOrchestrationError
from epos.domain.ids import EntityId
from epos.domain.outfit import OutfitItem, OutfitState, WardrobeOutfit
from epos.domain.world_state import WorldState


def _canonical_outfit(
    state: WorldState,
    *,
    actor_id: EntityId,
    outfit_id: str,
) -> OutfitState:
    definition = state.wardrobes.get(outfit_id)
    if definition is None or definition.owner_id != actor_id:
        raise TurnOrchestrationError(
            f"outfit {outfit_id} is not available to {actor_id}",
            code="turn.outfit.unavailable",
        )
    return OutfitState(items=tuple(item.model_copy(deep=True) for item in definition.items))


def _item_state_outfit(
    current: OutfitState,
    *,
    requested_state: str,
    item_ids: tuple[str, ...],
) -> OutfitState:
    selected = set(item_ids)
    items: list[OutfitItem] = []
    for item in current.items:
        if item.item_id not in selected:
            items.append(item.model_copy(deep=True))
            continue
        new_state = "removed" if requested_state == "remove_items" else None
        items.append(
            OutfitItem.model_validate(
                {**item.model_dump(mode="python"), "state": new_state}
            )
        )
    return OutfitState(items=tuple(items))


def outfit_from_validated_request(
    state: WorldState,
    *,
    request: ValidatedOutfitRequest,
    current: OutfitState,
    selected_outfit_id: str | None = None,
) -> OutfitState:
    if request.requested_state == "wear_outfit":
        selected = selected_outfit_id
        if selected is None or selected not in request.candidate_outfit_ids:
            raise TurnOrchestrationError(
                "outfit choice is not Python-authorized",
                code="turn.outfit.choice_not_authorized",
            )
        return _canonical_outfit(state, actor_id=request.target_id, outfit_id=selected)
    return _item_state_outfit(
        current,
        requested_state=request.requested_state,
        item_ids=request.item_ids,
    )


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
    return normalized or "outfit"


def _generated_outfit(
    state: WorldState,
    *,
    request: ValidatedOutfitRequest,
    proposal: GeneratedOutfitProposal,
) -> WardrobeOutfit:
    concept = request.requested_concept or proposal.name
    base_id = f"{_slug(str(request.target_id))}_{_slug(concept)}"
    outfit_id = base_id
    suffix = 2
    while outfit_id in state.wardrobes:
        outfit_id = f"{base_id}_{suffix}"
        suffix += 1

    seen_item_ids: set[str] = set()
    items: list[OutfitItem] = []
    for index, item in enumerate(proposal.items, start=1):
        item_base = f"{outfit_id}_{_slug(item.name)}"
        item_id = item_base
        if item_id in seen_item_ids:
            item_id = f"{item_base}_{index}"
        seen_item_ids.add(item_id)
        items.append(
            OutfitItem(
                item_id=item_id,
                name=item.name,
                slot=item.slot,
                layer=item.layer,
                coverage=item.coverage,
                material=item.material,
                color=item.color,
            )
        )

    tags = tuple(
        dict.fromkeys(
            (
                "generated",
                *request.semantic_tags,
                *proposal.tags,
                _slug(concept),
            )
        )
    )
    return WardrobeOutfit(
        outfit_id=outfit_id,
        owner_id=request.target_id,
        tags=tags,
        items=tuple(items),
    )


class PythonNPCOutfitMutationPlanner:
    """Convert validated NPC choices into engine-owned persistent outfit state."""

    def plan(
        self,
        *,
        state: WorldState,
        action_request: ValidatedOutfitRequest | None,
        reactions: tuple[CognitionResult, ...],
    ) -> MutationBatch:
        mutations: list[StateMutation] = []
        for result in reactions:
            reaction = result.reaction
            npc_id = reaction.npc_id
            npc = state.npcs[npc_id]
            response = reaction.outfit_request_response
            if (
                response is not None
                and response.disposition is OutfitRequestDisposition.ACCEPTED
                and action_request is not None
                and action_request.target_id == npc_id
            ):
                if response.generated_outfit is not None:
                    generated = _generated_outfit(
                        state,
                        request=action_request,
                        proposal=response.generated_outfit,
                    )
                    mutations.append(UpsertWardrobeOutfitMutation(outfit=generated))
                    mutations.append(
                        ReplaceNPCOutfitMutation(
                            npc_id=npc_id,
                            outfit=OutfitState(
                                items=tuple(
                                    item.model_copy(deep=True) for item in generated.items
                                )
                            ),
                        )
                    )
                    continue
                outfit = outfit_from_validated_request(
                    state,
                    request=action_request,
                    current=npc.outfit,
                    selected_outfit_id=response.selected_outfit_id,
                )
                mutations.append(ReplaceNPCOutfitMutation(npc_id=npc_id, outfit=outfit))
                continue

            autonomous = reaction.autonomous_outfit_action
            if autonomous is not None:
                outfit = self._autonomous_outfit(
                    state=state,
                    npc_id=npc_id,
                    current=npc.outfit,
                    action=autonomous,
                )
                mutations.append(ReplaceNPCOutfitMutation(npc_id=npc_id, outfit=outfit))

        return MutationBatch(
            producer=MutationAuthority.ENGINE_ONLY,
            mutations=tuple(mutations),
        )

    @staticmethod
    def _autonomous_outfit(
        *,
        state: WorldState,
        npc_id: EntityId,
        current: OutfitState,
        action: NPCOutfitAction,
    ) -> OutfitState:
        if action.requested_state == "wear_outfit":
            if action.outfit_id is None:
                raise TurnOrchestrationError(
                    "validated NPC outfit action lost outfit_id",
                    code="turn.outfit.invalid_validated_action",
                )
            return _canonical_outfit(state, actor_id=npc_id, outfit_id=action.outfit_id)
        return _item_state_outfit(
            current,
            requested_state=action.requested_state,
            item_ids=action.item_ids,
        )

from __future__ import annotations

import pytest

from epos.application.actions import (
    ActionInterpretation,
    ActionInterpreterContext,
    ActionValidator,
    ObservationIntent,
    OutfitRequestProposal,
)
from epos.application.cognition import (
    CognitionResult,
    CognitionScene,
    CognitionValidationError,
    GeneratedOutfitItemProposal,
    GeneratedOutfitProposal,
    NPCOutfitAction,
    NPCOutfitRequestResponse,
    NPCReactionProposal,
    NPCReactionValidator,
    OutfitRequestDisposition,
    PrivateCognitiveContextBuilder,
)
from epos.application.memory import MemoryRecallResult
from epos.application.state.mutations import apply_mutation
from epos.application.turn import PythonNPCOutfitMutationPlanner
from epos.application.visual import ObservableSceneBuilder, SceneObservationInput
from epos.domain.ids import EntityId, LocationId, SessionId, WorldpackId
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.outfit import OutfitItem, OutfitState, WardrobeOutfit
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, WorldState

LUNA = EntityId("luna")
PLAYER = EntityId("player")


def _world() -> WorldState:
    shoes = OutfitItem(
        item_id="luna_shoes",
        name="black heels",
        slot="feet",
        layer=20,
        coverage=("feet",),
        color="black",
    )
    socks = OutfitItem(
        item_id="luna_socks",
        name="ankle socks",
        slot="feet",
        layer=10,
        coverage=("feet",),
        color="white",
    )
    return WorldState(
        session_id=SessionId("session-outfit"),
        worldpack_id=WorldpackId("resort-world"),
        turn_number=8,
        day=2,
        world_phase="evening",
        player=PlayerState(
            entity_id=PLAYER,
            name="Player",
            location_id=LocationId("suite"),
        ),
        npcs={
            LUNA: NPCState(
                identity=NPCIdentity(entity_id=LUNA, name="Luna", role="companion"),
                location_id=LocationId("suite"),
                outfit=OutfitState(items=(socks, shoes)),
            )
        },
        locations={
            LocationId("suite"): LocationState(
                location_id=LocationId("suite"),
                name="Suite",
            )
        },
        wardrobes={
            "luna_supergirl": WardrobeOutfit(
                outfit_id="luna_supergirl",
                owner_id=LUNA,
                tags=("costume", "superhero"),
                items=(
                    OutfitItem(
                        item_id="supergirl_dress",
                        name="Supergirl dress",
                        slot="body",
                        layer=10,
                        coverage=("torso", "hips"),
                    ),
                ),
            ),
            "luna_evening": WardrobeOutfit(
                outfit_id="luna_evening",
                owner_id=LUNA,
                tags=("sexy", "elegant"),
                items=(
                    OutfitItem(
                        item_id="evening_dress",
                        name="fitted evening dress",
                        slot="body",
                        layer=10,
                    ),
                ),
            ),
        },
    )


def _context(player_input: str) -> ActionInterpreterContext:
    return ActionInterpreterContext.from_world_state(
        _world(),
        player_input=player_input,
        known_location_ids=(LocationId("suite"),),
    )


def _validate(proposal: ActionInterpretation, player_input: str = ""):
    return ActionValidator().validate(proposal, _context(player_input or proposal.intent))


def _cognition_context(action):
    state = _world()
    return PrivateCognitiveContextBuilder().build(
        state=state,
        npc_id=LUNA,
        scene=CognitionScene(
            location_id=LocationId("suite"),
            present_entity_ids=(PLAYER, LUNA),
        ),
        player_input="Luna, mettiti qualcosa di sexy",
        action=action,
        recalled=MemoryRecallResult(query_text="", memories=()),
        resolved_check=None,
    )


def _reaction(**kwargs):
    return NPCReactionProposal(
        npc_id=LUNA,
        intent="respond",
        speech_act="answer",
        **kwargs,
    )


def test_observation_intent_preserves_player_requested_body_region() -> None:
    action = _validate(
        ActionInterpretation(
            intent="observe",
            target_ids=(LUNA,),
            observation=ObservationIntent(subject_id=LUNA, region="feet"),
        ),
        "Osservo i piedi di Luna",
    )

    scene = ObservableSceneBuilder().build(
        state=_world(),
        observation=SceneObservationInput(action=action),
    )

    assert scene.visual_focus_candidate is not None
    assert scene.visual_focus_candidate.subject_ids == (LUNA,)
    assert scene.visual_focus_candidate.region == "feet"
    assert scene.visual_focus_candidate.reason == "player_observation"


def test_exact_and_semantic_outfit_requests_resolve_only_canonical_candidates() -> None:
    exact = _validate(
        ActionInterpretation(
            intent="request_outfit_change",
            target_ids=(LUNA,),
            outfit_request=OutfitRequestProposal(
                target_id=LUNA,
                requested_state="wear_outfit",
                outfit_id="luna_supergirl",
            ),
        )
    )
    semantic = _validate(
        ActionInterpretation(
            intent="request_outfit_change",
            target_ids=(LUNA,),
            outfit_request=OutfitRequestProposal(
                target_id=LUNA,
                requested_state="wear_outfit",
                semantic_tags=("sexy",),
            ),
        )
    )

    assert exact.outfit_request is not None
    assert exact.outfit_request.candidate_outfit_ids == ("luna_supergirl",)
    assert semantic.outfit_request is not None
    assert semantic.outfit_request.candidate_outfit_ids == ("luna_evening",)


def test_npc_cannot_accept_with_an_unstructured_invented_outfit_id() -> None:
    action = _validate(
        ActionInterpretation(
            intent="request_outfit_change",
            target_ids=(LUNA,),
            outfit_request=OutfitRequestProposal(
                target_id=LUNA,
                requested_state="wear_outfit",
                semantic_tags=("sexy",),
            ),
        )
    )
    proposal = _reaction(
        outfit_request_response=NPCOutfitRequestResponse(
            disposition=OutfitRequestDisposition.ACCEPTED,
            selected_outfit_id="invented_red_dress",
        )
    )

    with pytest.raises(CognitionValidationError, match="Python-authorized"):
        NPCReactionValidator().validate(proposal, _cognition_context(action))


def test_missing_catwoman_outfit_can_be_generated_and_persisted() -> None:
    state = _world()
    action = _validate(
        ActionInterpretation(
            intent="request_outfit_change",
            target_ids=(LUNA,),
            outfit_request=OutfitRequestProposal(
                target_id=LUNA,
                requested_state="wear_outfit",
                outfit_id="catwoman",
            ),
        ),
        "Luna, indossa un abito da Catwoman",
    )
    assert action.outfit_request is not None
    assert action.outfit_request.candidate_outfit_ids == ()
    assert action.outfit_request.requested_concept == "catwoman"
    assert action.outfit_request.allow_generated_outfit is True

    proposal = _reaction(
        outfit_request_response=NPCOutfitRequestResponse(
            disposition=OutfitRequestDisposition.ACCEPTED,
            generated_outfit=GeneratedOutfitProposal(
                name="Catwoman-inspired catsuit",
                tags=("costume", "catwoman"),
                items=(
                    GeneratedOutfitItemProposal(
                        name="black fitted catsuit",
                        slot="body",
                        layer=10,
                        coverage=("torso", "arms", "legs"),
                        material="shiny faux leather",
                        color="black",
                    ),
                    GeneratedOutfitItemProposal(
                        name="cat ear mask",
                        slot="head",
                        layer=20,
                        coverage=("eyes", "head"),
                        color="black",
                    ),
                ),
            ),
        )
    )
    validated = NPCReactionValidator().validate(proposal, _cognition_context(action))
    plan = PythonNPCOutfitMutationPlanner().plan(
        state=state,
        action_request=action.outfit_request,
        reactions=(CognitionResult(reaction=validated),),
    )

    assert tuple(mutation.kind for mutation in plan.mutations) == (
        "upsert_wardrobe_outfit",
        "replace_npc_outfit",
    )
    for mutation in plan.mutations:
        apply_mutation(state, mutation)

    generated = state.wardrobes["luna_catwoman"]
    assert generated.owner_id == LUNA
    assert "generated" in generated.tags
    assert "catwoman" in generated.tags
    assert state.npcs[LUNA].outfit == OutfitState(items=generated.items)
    assert tuple(item.name for item in generated.items) == (
        "black fitted catsuit",
        "cat ear mask",
    )


def test_llm_cannot_generate_replacement_when_matching_outfit_exists() -> None:
    action = _validate(
        ActionInterpretation(
            intent="request_outfit_change",
            target_ids=(LUNA,),
            outfit_request=OutfitRequestProposal(
                target_id=LUNA,
                requested_state="wear_outfit",
                outfit_id="luna_supergirl",
            ),
        )
    )
    proposal = _reaction(
        outfit_request_response=NPCOutfitRequestResponse(
            disposition=OutfitRequestDisposition.ACCEPTED,
            generated_outfit=GeneratedOutfitProposal(
                name="Improvised superhero dress",
                items=(
                    GeneratedOutfitItemProposal(
                        name="red cape",
                        slot="back",
                        layer=20,
                    ),
                ),
            ),
        )
    )

    with pytest.raises(CognitionValidationError, match="canonical candidates exist"):
        NPCReactionValidator().validate(proposal, _cognition_context(action))


def test_accepted_npc_choice_becomes_persistent_authoritative_outfit() -> None:
    state = _world()
    action = _validate(
        ActionInterpretation(
            intent="request_outfit_change",
            target_ids=(LUNA,),
            outfit_request=OutfitRequestProposal(
                target_id=LUNA,
                requested_state="wear_outfit",
                semantic_tags=("sexy",),
            ),
        )
    )
    proposal = _reaction(
        outfit_request_response=NPCOutfitRequestResponse(
            disposition=OutfitRequestDisposition.ACCEPTED,
            selected_outfit_id="luna_evening",
        )
    )
    validated = NPCReactionValidator().validate(proposal, _cognition_context(action))
    plan = PythonNPCOutfitMutationPlanner().plan(
        state=state,
        action_request=action.outfit_request,
        reactions=(CognitionResult(reaction=validated),),
    )

    assert len(plan.mutations) == 1
    apply_mutation(state, plan.mutations[0])
    assert tuple(item.item_id for item in state.npcs[LUNA].outfit.items) == (
        "evening_dress",
    )


def test_autonomous_shoe_removal_persists_but_socks_remain_visible() -> None:
    state = _world()
    action = _validate(ActionInterpretation(intent="dialogue", target_ids=(LUNA,)))
    proposal = _reaction(
        autonomous_outfit_action=NPCOutfitAction(
            requested_state="remove_items",
            item_ids=("luna_shoes",),
        )
    )
    validated = NPCReactionValidator().validate(proposal, _cognition_context(action))
    plan = PythonNPCOutfitMutationPlanner().plan(
        state=state,
        action_request=None,
        reactions=(CognitionResult(reaction=validated),),
    )
    apply_mutation(state, plan.mutations[0])

    outfit = state.npcs[LUNA].outfit
    assert next(item for item in outfit.items if item.item_id == "luna_shoes").state == "removed"
    assert tuple(item.item_id for item in outfit.visible_items()) == ("luna_socks",)


def test_rejected_outfit_request_produces_no_outfit_mutation() -> None:
    action = _validate(
        ActionInterpretation(
            intent="request_outfit_change",
            target_ids=(LUNA,),
            outfit_request=OutfitRequestProposal(
                target_id=LUNA,
                requested_state="wear_outfit",
                outfit_id="luna_supergirl",
            ),
        )
    )
    validated = NPCReactionValidator().validate(
        _reaction(
            outfit_request_response=NPCOutfitRequestResponse(
                disposition=OutfitRequestDisposition.REJECTED
            )
        ),
        _cognition_context(action),
    )
    plan = PythonNPCOutfitMutationPlanner().plan(
        state=_world(),
        action_request=action.outfit_request,
        reactions=(CognitionResult(reaction=validated),),
    )

    assert plan.mutations == ()

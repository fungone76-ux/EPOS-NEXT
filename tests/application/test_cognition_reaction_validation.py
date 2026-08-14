from __future__ import annotations

import pytest
from pydantic import ValidationError

from epos.application.actions.models import ValidatedAction
from epos.application.cognition.context import PrivateCognitiveContextBuilder
from epos.application.cognition.models import CognitionScene, NPCReactionProposal
from epos.application.cognition.validation import CognitionValidationError, NPCReactionValidator
from epos.application.memory import MemoryRecallResult, RankedMemory
from epos.domain.ids import EntityId, LocationId, MemoryId, SessionId, TurnNumber, WorldpackId
from epos.domain.memory import MemoryEntryState
from epos.domain.npc import DisclosureRule, NPCIdentity, NPCState, SecretState
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, WorldState


def _context() -> object:
    player_id = EntityId("player")
    victoria_id = EntityId("victoria")
    lobby = LocationId("lobby")
    npc = NPCState(
        identity=NPCIdentity(entity_id=victoria_id, name="Victoria", role="host"),
        location_id=lobby,
        secrets=(SecretState(secret_id="letter", fact="The letter is in the office."),),
        disclosure_rules=(DisclosureRule(secret_id="letter", required_flags=("unlock_letter",)),),
    )
    state = WorldState(
        session_id=SessionId("s"),
        worldpack_id=WorldpackId("resort_world"),
        turn_number=TurnNumber(8),
        day=1,
        world_phase="evening",
        player=PlayerState(entity_id=player_id, name="Alex", location_id=lobby),
        npcs={victoria_id: npc},
        locations={lobby: LocationState(location_id=lobby, name="Lobby")},
        flags={"unlock_letter": False},
    )
    memory = MemoryEntryState(
        memory_id=MemoryId("m1"),
        turn=TurnNumber(3),
        summary="The player kept a promise.",
        participants=(player_id, victoria_id),
        salience=8.0,
    )
    return PrivateCognitiveContextBuilder().build(
        state=state,
        npc_id=victoria_id,
        scene=CognitionScene(
            location_id=lobby,
            present_entity_ids=(player_id, victoria_id),
            summary="Lobby.",
        ),
        player_input="Buona sera Victoria.",
        action=ValidatedAction(intent="dialogue", target_ids=(victoria_id,)),
        recalled=MemoryRecallResult(
            query_text="greeting",
            memories=(RankedMemory(memory=memory, semantic_score=0.8, relevance_score=0.9),),
        ),
        resolved_check=None,
    )


def test_reaction_contract_rejects_private_chain_of_thought_fields() -> None:
    with pytest.raises(ValidationError):
        NPCReactionProposal.model_validate(
            {
                "npc_id": "victoria",
                "intent": "respond_to_greeting",
                "communication_goal": "return the greeting",
                "chain_of_thought": "I remember the promise, therefore...",
            }
        )


def test_validator_rejects_locked_secret_disclosure() -> None:
    proposal = NPCReactionProposal(
        npc_id=EntityId("victoria"),
        intent="respond",
        communication_goal="mention the hidden letter",
        requested_secret_disclosures=("letter",),
    )

    with pytest.raises(CognitionValidationError, match="secret.*letter"):
        NPCReactionValidator().validate(proposal, _context())


def test_validator_rejects_memory_reference_not_in_recall_context() -> None:
    proposal = NPCReactionProposal(
        npc_id=EntityId("victoria"),
        intent="respond",
        communication_goal="refer to a memory",
        referenced_memory_ids=(MemoryId("unknown"),),
    )

    with pytest.raises(CognitionValidationError, match="memory.*unknown"):
        NPCReactionValidator().validate(proposal, _context())


def test_validator_accepts_structured_non_authoritative_reaction() -> None:
    proposal = NPCReactionProposal(
        npc_id=EntityId("victoria"),
        intent="respond_to_greeting",
        communication_goal="return the greeting with reserved warmth",
        emotional_tone=("reserved", "warm"),
        referenced_memory_ids=(MemoryId("m1"),),
        target_ids=(EntityId("player"),),
    )

    validated = NPCReactionValidator().validate(proposal, _context())

    assert validated.intent == "respond_to_greeting"
    assert validated.referenced_memory_ids == (MemoryId("m1"),)

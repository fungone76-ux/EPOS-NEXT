from __future__ import annotations

from epos.application.actions.models import ValidatedAction
from epos.application.cognition.context import PrivateCognitiveContextBuilder
from epos.application.cognition.models import CognitionScene
from epos.application.memory import MemoryRecallResult, RankedMemory
from epos.domain.character_definition import ConditionalBehavior, ExampleDialogue, NPCCharacterDefinition
from epos.domain.ids import EntityId, LocationId, MemoryId, SessionId, TurnNumber, WorldpackId
from epos.domain.knowledge import KnowledgeState
from epos.domain.memory import MemoryEntryState, MemoryKind
from epos.domain.npc import DisclosureRule, NPCIdentity, NPCState, SecretState
from epos.domain.player import PlayerState
from epos.domain.relationships import RelationshipState
from epos.domain.world_state import LocationState, WorldState


def _memory(
    memory_id: str,
    summary: str,
    *,
    turn: int,
    kind: MemoryKind = MemoryKind.EPISODIC,
) -> MemoryEntryState:
    return MemoryEntryState(
        memory_id=MemoryId(memory_id),
        turn=TurnNumber(turn),
        summary=summary,
        participants=(EntityId("player"), EntityId("victoria")),
        salience=8.0,
        kind=kind,
    )


def _state(*, trust: float = 6.0, unlocked: bool = False) -> WorldState:
    player_id = EntityId("player")
    victoria_id = EntityId("victoria")
    stella_id = EntityId("stella")
    lobby = LocationId("lobby")
    victoria = NPCState(
        identity=NPCIdentity(entity_id=victoria_id, name="Victoria", role="host"),
        location_id=lobby,
        character_definition=NPCCharacterDefinition(
            short_description="An elegant, controlled resort host.",
            long_description="Victoria is strategic, observant, proud, and rarely impulsive.",
            personality=("controlled", "observant", "strategic"),
            speech_style="Precise, concise, dryly ironic; never chatty without reason.",
            values=("self-control", "loyalty"),
            relationship_tendencies=("Low trust makes her guarded rather than openly hostile.",),
            conditional_behaviors=(
                ConditionalBehavior(
                    condition="angry",
                    guidance=("becomes colder and shorter", "does not suddenly shout"),
                ),
            ),
            example_dialogues=(
                ExampleDialogue(
                    player="Ti sono mancato?",
                    npc="Non montarti la testa. Ho solo notato il silenzio.",
                ),
            ),
            never_behaviors=("beg for approval",),
        ),
        personality=("controlled", "observant"),
        speech_style="precise",
        goals=("protect the resort",),
        fears=("public scandal",),
        knowledge=KnowledgeState(facts={"luna_role": "guest"}),
        beliefs=KnowledgeState(facts={"player_reliable": True}),
        false_beliefs=KnowledgeState(facts={"storm_tomorrow": True}),
        secrets=(SecretState(secret_id="letter", fact="Luna hid a letter in the office."),),
        disclosure_rules=(
            DisclosureRule(
                secret_id="letter",
                required_flags=("letter_topic_unlocked",),
                trust_min=7.0,
            ),
        ),
        relationships={player_id: RelationshipState(trust=trust)},
        short_term_memory=(_memory("recent", "The player greeted Victoria.", turn=9),),
        core_memories=(
            _memory(
                "core",
                "The player once protected Victoria.",
                turn=2,
                kind=MemoryKind.CORE,
            ),
        ),
    )
    stella = NPCState(
        identity=NPCIdentity(entity_id=stella_id, name="Stella", role="guest"),
        location_id=lobby,
        knowledge=KnowledgeState(facts={"stella_private_code": "S-19"}),
        secrets=(SecretState(secret_id="stella_secret", fact="Stella owns the hidden key."),),
    )
    return WorldState(
        session_id=SessionId("session"),
        worldpack_id=WorldpackId("resort_world"),
        turn_number=TurnNumber(10),
        day=1,
        world_phase="evening",
        player=PlayerState(entity_id=player_id, name="Alex", location_id=lobby),
        npcs={victoria_id: victoria, stella_id: stella},
        locations={lobby: LocationState(location_id=lobby, name="Lobby")},
        flags={"letter_topic_unlocked": unlocked},
        world_truth=KnowledgeState(facts={"global_hidden_truth": "classified"}),
    )


def test_private_context_contains_only_target_npc_private_state() -> None:
    recalled = _memory("promise", "The player promised to return the key.", turn=4)
    recall = MemoryRecallResult(
        query_text="return key",
        memories=(RankedMemory(memory=recalled, semantic_score=0.9, relevance_score=0.95),),
    )
    scene = CognitionScene(
        location_id=LocationId("lobby"),
        present_entity_ids=(EntityId("player"), EntityId("victoria"), EntityId("stella")),
        observable_facts=("The player is speaking to Victoria.",),
        summary="Evening in the lobby.",
    )

    context = PrivateCognitiveContextBuilder().build(
        state=_state(),
        npc_id=EntityId("victoria"),
        scene=scene,
        player_input="Victoria, cosa sai di Luna?",
        action=ValidatedAction(intent="dialogue", target_ids=(EntityId("victoria"),)),
        recalled=recall,
        resolved_check=None,
    )

    dumped = context.model_dump_json()
    assert context.player_input == "Victoria, cosa sai di Luna?"
    assert context.knowledge.facts == {"luna_role": "guest"}
    assert context.recalled_memories[0].memory.memory_id == MemoryId("promise")
    assert "global_hidden_truth" not in dumped
    assert "stella_private_code" not in dumped
    assert "Stella owns the hidden key" not in dumped
    assert context.secrets[0].secret_id == "letter"
    assert context.secrets[0].disclosure_allowed is False


def test_character_definition_is_available_to_npc_reasoning() -> None:
    context = PrivateCognitiveContextBuilder().build(
        state=_state(),
        npc_id=EntityId("victoria"),
        scene=CognitionScene(
            location_id=LocationId("lobby"),
            present_entity_ids=(EntityId("player"), EntityId("victoria")),
            summary="Lobby.",
        ),
        player_input="Ti sono mancato?",
        action=ValidatedAction(intent="dialogue", target_ids=(EntityId("victoria"),)),
        recalled=MemoryRecallResult(query_text="mancato", memories=()),
        resolved_check=None,
    )

    definition = context.character_definition
    assert definition.short_description == "An elegant, controlled resort host."
    assert definition.example_dialogues[0].npc.startswith("Non montarti la testa")
    assert definition.conditional_behaviors[0].condition == "angry"
    assert definition.never_behaviors == ("beg for approval",)


def test_disclosure_permission_is_python_derived_from_flags_and_relationship() -> None:
    context = PrivateCognitiveContextBuilder().build(
        state=_state(trust=8.0, unlocked=True),
        npc_id=EntityId("victoria"),
        scene=CognitionScene(
            location_id=LocationId("lobby"),
            present_entity_ids=(EntityId("player"), EntityId("victoria")),
            summary="Lobby.",
        ),
        player_input="Parliamo della lettera.",
        action=ValidatedAction(intent="dialogue", target_ids=(EntityId("victoria"),)),
        recalled=MemoryRecallResult(query_text="lettera", memories=()),
        resolved_check=None,
    )

    assert context.secrets[0].disclosure_allowed is True

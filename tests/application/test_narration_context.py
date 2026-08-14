from __future__ import annotations

import pytest

from epos.application.actions.models import ValidatedAction
from epos.application.cognition.models import ValidatedNPCReaction
from epos.application.conversation.context import NarrationContextBuilder, NarrationContextError
from epos.application.conversation.models import (
    ConversationFocus,
    NarratableMemory,
    NarrationEvidenceKind,
    NarrationKnowledgeSelection,
    NarrationKnowledgeSource,
    NarrationMode,
)
from epos.application.visual import (
    ObservableConsequence,
    ObservableSceneBuilder,
    SceneObservationInput,
)
from epos.domain.ids import EntityId, LocationId, MemoryId, SessionId, TurnNumber, WorldpackId
from epos.domain.knowledge import KnowledgeState
from epos.domain.memory import MemoryEntryState
from epos.domain.npc import NPCIdentity, NPCState, SecretState
from epos.domain.player import PlayerState
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState
from epos.domain.world_state import LocationState, WorldState


def _state() -> WorldState:
    player_id = EntityId("player")
    victoria_id = EntityId("victoria")
    stella_id = EntityId("stella")
    lobby = LocationId("lobby")
    return WorldState(
        session_id=SessionId("session"),
        worldpack_id=WorldpackId("resort_world"),
        turn_number=TurnNumber(40),
        day=3,
        world_phase="evening",
        player=PlayerState(entity_id=player_id, name="Alex", location_id=lobby),
        npcs={
            victoria_id: NPCState(
                identity=NPCIdentity(
                    entity_id=victoria_id,
                    name="Victoria",
                    role="host",
                ),
                location_id=lobby,
                personality=("controlled", "elegant"),
                speech_style="precise and restrained",
                knowledge=KnowledgeState(facts={"luna_role": "Luna dirige il resort."}),
                secrets=(
                    SecretState(
                        secret_id="letter",
                        fact="La lettera è nel cassetto rosso.",
                    ),
                ),
                emotional_state=EmotionalState(anger=3.0, joy=5.0),
                relationships={
                    player_id: RelationshipState(trust=6.0, affection=4.0)
                },
            ),
            stella_id: NPCState(
                identity=NPCIdentity(
                    entity_id=stella_id,
                    name="Stella",
                    role="guest",
                ),
                location_id=lobby,
                knowledge=KnowledgeState(
                    facts={"private_stella": "Stella teme il temporale."}
                ),
                secrets=(
                    SecretState(
                        secret_id="stella_secret",
                        fact="Solo Stella lo sa.",
                    ),
                ),
            ),
        },
        locations={lobby: LocationState(location_id=lobby, name="Lobby")},
        world_truth=KnowledgeState(
            facts={"hidden_world_truth": "Il direttore mente."}
        ),
    )


def _focus() -> ConversationFocus:
    return ConversationFocus(
        speaker_id=EntityId("player"),
        target_npc_id=EntityId("victoria"),
        topic="luna",
        mode=NarrationMode.DIRECT_DIALOGUE,
    )


def _reaction(
    *,
    secrets: tuple[str, ...] = (),
    memories: tuple[MemoryId, ...] = (),
) -> ValidatedNPCReaction:
    return ValidatedNPCReaction(
        npc_id=EntityId("victoria"),
        intent="answer_question",
        speech_act="inform",
        topic_tags=("luna",),
        emotional_tone=("controlled",),
        target_ids=(EntityId("player"),),
        referenced_memory_ids=memories,
        authorized_secret_disclosures=secrets,
    )


def _scene():
    state = _state()
    return ObservableSceneBuilder().build(
        state=state,
        observation=SceneObservationInput(
            action=ValidatedAction(
                intent="dialogue",
                target_ids=(EntityId("victoria"),),
            ),
            observable_consequences=(
                ObservableConsequence(
                    consequence_id="lobby_quiet",
                    kind="environment",
                    fact="La hall è tranquilla.",
                ),
            ),
        ),
    )


def _build(
    *,
    reaction: ValidatedNPCReaction,
    knowledge: tuple[NarrationKnowledgeSelection, ...] = (),
    memories: tuple[NarratableMemory, ...] = (),
):
    return NarrationContextBuilder().build(
        state=_state(),
        scene=_scene(),
        focus=_focus(),
        player_input="Victoria, cosa sai di Luna?",
        reactions=(reaction,),
        knowledge_selections=knowledge,
        narratable_memories=memories,
    )


def test_narration_context_uses_observable_scene_as_single_action_source() -> None:
    context = _build(reaction=_reaction())

    assert context.scene.resolved_action.action.intent == "dialogue"
    assert context.scene.resolved_action.action.target_ids == (EntityId("victoria"),)
    assert context.scene.resolved_action.resolved_check is None
    assert not hasattr(context, "action")
    assert not hasattr(context, "resolved_check")


def test_narration_context_excludes_world_truth_other_npc_private_state_and_locked_secret() -> None:
    context = _build(reaction=_reaction())
    serialized = context.model_dump_json()

    assert "hidden_world_truth" not in serialized
    assert "private_stella" not in serialized
    assert "stella_secret" not in serialized
    assert "cassetto rosso" not in serialized


def test_context_contains_voice_emotion_relationship_and_selected_safe_knowledge() -> None:
    context = _build(
        reaction=_reaction(),
        knowledge=(
            NarrationKnowledgeSelection(
                npc_id=EntityId("victoria"),
                source=NarrationKnowledgeSource.KNOWLEDGE,
                keys=("luna_role",),
            ),
        ),
    )

    voice = context.voices[0]
    assert voice.npc_id == EntityId("victoria")
    assert voice.personality == ("controlled", "elegant")
    assert voice.speech_style == "precise and restrained"
    assert voice.emotional_state.joy == 5.0
    assert voice.relationship_with_player.trust == 6.0
    evidence = {item.evidence_id: item for item in context.evidence}
    safe = evidence["npc:victoria:knowledge:luna_role"]
    assert safe.kind is NarrationEvidenceKind.NPC_KNOWLEDGE
    assert safe.owner_id == EntityId("victoria")
    assert safe.text == "Luna dirige il resort."
    assert evidence["scene:consequence:lobby_quiet"].text == "La hall è tranquilla."


def test_only_authorized_secret_is_exposed_as_private_narration_evidence() -> None:
    context = _build(reaction=_reaction(secrets=("letter",)))
    evidence = {item.evidence_id: item for item in context.evidence}

    secret = evidence["npc:victoria:secret:letter"]
    assert secret.kind is NarrationEvidenceKind.AUTHORIZED_SECRET
    assert secret.owner_id == EntityId("victoria")
    assert secret.text == "La lettera è nel cassetto rosso."


def test_memory_text_is_not_exposed_automatically_even_when_cognition_referenced_it() -> None:
    context = _build(reaction=_reaction(memories=(MemoryId("promise"),)))

    assert all(
        item.kind is not NarrationEvidenceKind.NPC_MEMORY
        for item in context.evidence
    )


def test_narratable_memory_must_belong_to_reaction_reference_whitelist() -> None:
    memory = MemoryEntryState(
        memory_id=MemoryId("unrelated"),
        turn=TurnNumber(10),
        summary="Un ricordo privato non richiesto.",
    )

    with pytest.raises(NarrationContextError, match="memory"):
        _build(
            reaction=_reaction(memories=(MemoryId("promise"),)),
            memories=(
                NarratableMemory(
                    owner_id=EntityId("victoria"),
                    memory=memory,
                ),
            ),
        )

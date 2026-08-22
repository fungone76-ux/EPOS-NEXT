"""Live probe for character definition through cognition, validation, and narration."""

from __future__ import annotations

import asyncio

from dotenv import load_dotenv

from epos.application.actions.models import ValidatedAction
from epos.application.cognition.models import (
    NPCReactionProposal,
    PrivateCognitiveContext,
)
from epos.application.cognition.validation import NPCReactionValidator
from epos.application.conversation.audit import NarrationAuditValidator
from epos.application.conversation.models import (
    ConversationFocus,
    NarrationAuditContext,
    NarrationAuditProposal,
    NarrationContext,
    NarrationEvidence,
    NarrationEvidenceKind,
    NarrationMode,
    NarrationProposal,
    NPCNarrationVoice,
)
from epos.application.conversation.narration import NarrationComposer
from epos.application.conversation.validation import NarrationValidator
from epos.application.visual.models import (
    ObservableSceneState,
    ObservableSubject,
    ResolvedSceneAction,
    SceneLocation,
    SceneTime,
    SubjectKind,
)
from epos.domain.bond import BondState
from epos.domain.character_definition import (
    ConditionalBehavior,
    ExampleDialogue,
    NPCCharacterDefinition,
)
from epos.domain.ids import EntityId, LocationId, SceneId, SessionId, TurnNumber, WorldpackId
from epos.domain.knowledge import KnowledgeState
from epos.domain.outfit import OutfitState
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState
from epos.domain.visual_state import VisualState
from epos.infrastructure.llm.models import LLMTask
from epos.infrastructure.llm.port import StructuredLLMPort
from epos.infrastructure.llm.runtime import build_llm_runtime_from_env

PLAYER_INPUT = "Non mi fido di te."
PLAYER_ID = EntityId("player")
LOCATION_ID = LocationId("resort_lobby")
SESSION_ID = SessionId("character_probe")
WORLDPACK_ID = WorldpackId("resort_world")
TURN = TurnNumber(1)


def _definition(name: str) -> NPCCharacterDefinition:
    if name == "Victoria":
        return NPCCharacterDefinition(
            short_description="Controlled, incisive resort executive.",
            long_description=(
                "Victoria is strategic, proud, observant and highly self-controlled. "
                "She dislikes emotional exposure and reacts to pressure by becoming colder."
            ),
            personality=("controlled", "strategic", "proud", "observant"),
            speech_style="Concise, precise, dry, restrained; rarely openly emotional.",
            values=("self-control", "competence", "loyalty"),
            relationship_tendencies=(
                "Low trust makes her guarded and challenging rather than pleading.",
            ),
            conditional_behaviors=(
                ConditionalBehavior(
                    condition="irritated",
                    guidance=("becomes colder", "uses sharper wording", "does not shout"),
                ),
            ),
            example_dialogues=(
                ExampleDialogue(
                    player="Sei arrabbiata?",
                    npc="No. Ma continua pure e potrei riconsiderare la risposta.",
                ),
            ),
            never_behaviors=("beg for approval", "become melodramatic"),
        )
    return NPCCharacterDefinition(
        short_description="Quick-witted, proud and emotionally transparent guest.",
        long_description=(
            "Stella is impulsive, ironic, proud and expressive. She reacts quickly when she "
            "feels judged and often uses humor or sarcasm to defend herself."
        ),
        personality=("impulsive", "sarcastic", "proud", "expressive"),
        speech_style="Informal, quick, ironic, provocative when irritated.",
        values=("independence", "honesty", "self-respect"),
        relationship_tendencies=(
            "Low trust makes her openly defensive and more sarcastic.",
        ),
        conditional_behaviors=(
            ConditionalBehavior(
                condition="irritated",
                guidance=("reacts immediately", "uses sarcasm", "shows irritation openly"),
            ),
        ),
        example_dialogues=(
            ExampleDialogue(
                player="Ti dà fastidio quello che penso?",
                npc="Certo. Ho costruito tutta la giornata attorno alla tua approvazione.",
            ),
        ),
        never_behaviors=("speak like a corporate executive", "hide every emotional reaction"),
    )


def _cognitive_context(name: str, npc_id: EntityId) -> PrivateCognitiveContext:
    definition = _definition(name)
    return PrivateCognitiveContext(
        npc_id=npc_id,
        npc_name=name,
        role="resort_guest" if name == "Stella" else "resort_executive",
        player_id=PLAYER_ID,
        character_definition=definition,
        personality=(),
        speech_style="",
        goals=("understand the player's intentions",),
        current_intentions=("evaluate_player",),
        emotional_state=EmotionalState(anger=3.5),
        relationship_with_player=RelationshipState(trust=4.0, suspicion=6.0),
        bond_state=BondState(),
        knowledge=KnowledgeState(facts={"player_is_guest": True}),
        beliefs=KnowledgeState(facts={"player_may_be_testing_me": True}),
        false_beliefs=KnowledgeState(),
        discoveries=KnowledgeState(),
        scene={
            "location_id": LOCATION_ID,
            "present_entity_ids": (PLAYER_ID, EntityId("victoria"), EntityId("stella")),
            "observable_facts": (
                "The player directly says they do not trust this NPC.",
            ),
            "summary": "Evening in the resort lobby.",
        },
        player_input=PLAYER_INPUT,
        action=ValidatedAction(intent="dialogue", target_ids=(npc_id,)),
    )


def _observable_scene(npc_id: EntityId, name: str) -> ObservableSceneState:
    action = ValidatedAction(intent="dialogue", target_ids=(npc_id,))
    return ObservableSceneState(
        scene_id=SceneId(f"{SESSION_ID}:{int(TURN)}"),
        session_id=SESSION_ID,
        worldpack_id=WORLDPACK_ID,
        location=SceneLocation(location_id=LOCATION_ID, name="Resort lobby"),
        time=SceneTime(turn_number=TURN, day=1, world_phase="evening"),
        visible_subjects=(
            ObservableSubject(
                entity_id=PLAYER_ID,
                kind=SubjectKind.PLAYER,
                name="Player",
                role="player",
                outfit=OutfitState(),
                visual_state=VisualState(),
            ),
            ObservableSubject(
                entity_id=npc_id,
                kind=SubjectKind.NPC,
                name=name,
                role="resort_guest" if name == "Stella" else "resort_executive",
                outfit=OutfitState(),
                visual_state=VisualState(),
            ),
        ),
        resolved_action=ResolvedSceneAction(action=action),
    )


def _narration_context(
    *,
    name: str,
    npc_id: EntityId,
    reaction: object,
) -> NarrationContext:
    from epos.application.cognition.models import ValidatedNPCReaction

    if not isinstance(reaction, ValidatedNPCReaction):
        raise TypeError("reaction must already be Python-validated")
    definition = _definition(name)
    scene = _observable_scene(npc_id, name)
    return NarrationContext(
        player_id=PLAYER_ID,
        player_input=PLAYER_INPUT,
        focus=ConversationFocus(
            speaker_id=PLAYER_ID,
            target_npc_id=npc_id,
            topic="trust",
            mode=NarrationMode.DIRECT_DIALOGUE,
        ),
        scene=scene,
        reactions=(reaction,),
        voices=(
            NPCNarrationVoice(
                npc_id=npc_id,
                name=name,
                personality=definition.personality,
                speech_style=definition.speech_style,
                emotional_state=EmotionalState(anger=3.5),
                relationship_with_player=RelationshipState(trust=4.0, suspicion=6.0),
            ),
        ),
        evidence=(
            NarrationEvidence(
                evidence_id="player:declared_input",
                kind=NarrationEvidenceKind.PLAYER_DECLARATION,
                text=PLAYER_INPUT,
                owner_id=PLAYER_ID,
            ),
            NarrationEvidence(
                evidence_id=f"reaction:{npc_id}",
                kind=NarrationEvidenceKind.NPC_REACTION,
                text=(
                    f"intent={reaction.intent}; speech_act={reaction.speech_act}; "
                    f"topics={','.join(reaction.topic_tags)}; "
                    f"tone={','.join(reaction.emotional_tone)}"
                ),
                owner_id=npc_id,
            ),
        ),
    )


async def _run() -> None:
    load_dotenv()
    runtime = build_llm_runtime_from_env()
    print("LLM diagnostic:")
    print(runtime.startup_diagnostic.model_dump_json(indent=2))
    if not runtime.backends:
        raise SystemExit("No LLM backend is configured.")

    cognition_port = StructuredLLMPort[PrivateCognitiveContext, NPCReactionProposal](
        task=LLMTask.REASON_NPC,
        response_model=NPCReactionProposal,
        runtime=runtime,
    )
    narration_port = StructuredLLMPort[NarrationContext, NarrationProposal](
        task=LLMTask.GENERATE_NARRATION,
        response_model=NarrationProposal,
        runtime=runtime,
    )
    audit_port = StructuredLLMPort[NarrationAuditContext, NarrationAuditProposal](
        task=LLMTask.AUDIT_NARRATION,
        response_model=NarrationAuditProposal,
        runtime=runtime,
    )
    reaction_validator = NPCReactionValidator()
    narration_validator = NarrationValidator()
    audit_validator = NarrationAuditValidator()
    composer = NarrationComposer()

    for name, raw_id in (("Victoria", "victoria"), ("Stella", "stella")):
        npc_id = EntityId(raw_id)
        cognition = _cognitive_context(name, npc_id)
        reaction_proposal = await cognition_port.invoke(cognition)
        reaction = reaction_validator.validate(reaction_proposal, cognition)
        narration_context = _narration_context(
            name=name,
            npc_id=npc_id,
            reaction=reaction,
        )
        narration_proposal = await narration_port.invoke(narration_context)
        validated_narration = narration_validator.validate(
            narration_proposal,
            narration_context,
        )
        audit_context = NarrationAuditContext(
            narration_context=narration_context,
            candidate=validated_narration,
        )
        audit = await audit_port.invoke(audit_context)
        audit_validator.validate(audit, validated_narration)
        text = composer.compose(validated_narration, narration_context)

        print(f"\n=== {name} ===")
        print("Reaction proposal JSON:")
        print(reaction_proposal.model_dump_json(indent=2))
        print("Validated reaction JSON:")
        print(reaction.model_dump_json(indent=2))
        print("Narration proposal JSON:")
        print(narration_proposal.model_dump_json(indent=2))
        print("Audit JSON:")
        print(audit.model_dump_json(indent=2))
        print("FINAL TEXT:")
        print(text)


if __name__ == "__main__":
    asyncio.run(_run())

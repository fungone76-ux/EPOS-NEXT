"""Live probe: same dynamic state, different stable NPC character definitions."""

from __future__ import annotations

import asyncio

from dotenv import load_dotenv

from epos.application.actions.models import ValidatedAction
from epos.application.cognition.models import CognitionScene, NPCReactionProposal, PrivateCognitiveContext
from epos.domain.bond import BondState
from epos.domain.character_definition import (
    ConditionalBehavior,
    ExampleDialogue,
    NPCCharacterDefinition,
)
from epos.domain.ids import EntityId, LocationId
from epos.domain.knowledge import KnowledgeState
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState
from epos.infrastructure.llm.models import LLMTask
from epos.infrastructure.llm.port import StructuredLLMPort
from epos.infrastructure.llm.runtime import build_llm_runtime_from_env

PLAYER_INPUT = "Non mi fido di te."


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


def _context(name: str, npc_id: str) -> PrivateCognitiveContext:
    player_id = EntityId("player")
    location_id = LocationId("resort_lobby")
    return PrivateCognitiveContext(
        npc_id=EntityId(npc_id),
        npc_name=name,
        role="resort_guest" if name == "Stella" else "resort_executive",
        player_id=player_id,
        character_definition=_definition(name),
        personality=(),
        speech_style="",
        desires=(),
        goals=("understand the player's intentions",),
        fears=(),
        red_lines=(),
        current_intentions=("evaluate_player",),
        emotional_state=EmotionalState(anger=3.5),
        relationship_with_player=RelationshipState(trust=4.0, suspicion=6.0),
        bond_state=BondState(),
        knowledge=KnowledgeState(facts={"player_is_guest": True}),
        beliefs=KnowledgeState(facts={"player_may_be_testing_me": True}),
        false_beliefs=KnowledgeState(),
        discoveries=KnowledgeState(),
        scene=CognitionScene(
            location_id=location_id,
            present_entity_ids=(player_id, EntityId("victoria"), EntityId("stella")),
            observable_facts=("The player directly says they do not trust this NPC.",),
            summary="Evening in the resort lobby.",
        ),
        player_input=PLAYER_INPUT,
        action=ValidatedAction(intent="dialogue", target_ids=(EntityId(npc_id),)),
    )


async def _run() -> None:
    load_dotenv()
    runtime = build_llm_runtime_from_env()
    print("LLM diagnostic:")
    print(runtime.startup_diagnostic.model_dump_json(indent=2))
    if not runtime.backends:
        raise SystemExit(
            "No LLM backend is configured in this worktree. Copy/configure .env first."
        )

    port = StructuredLLMPort[PrivateCognitiveContext, NPCReactionProposal](
        task=LLMTask.REASON_NPC,
        response_model=NPCReactionProposal,
        runtime=runtime,
    )

    for name, npc_id in (("Victoria", "victoria"), ("Stella", "stella")):
        context = _context(name, npc_id)
        print(f"\n=== {name} ===")
        print("Character definition:")
        print(context.character_definition.model_dump_json(indent=2))
        reaction = await port.invoke(context)
        print("Reaction JSON:")
        print(reaction.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(_run())

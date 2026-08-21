import pytest
from pydantic import ValidationError

from epos.domain.character_definition import ConditionalBehavior, ExampleDialogue, NPCCharacterDefinition


def test_character_definition_keeps_voice_examples_and_behavior_rules() -> None:
    definition = NPCCharacterDefinition(
        short_description="Controlled and incisive resort executive.",
        personality=("controlled", "strategic"),
        speech_style="Concise, dry, never melodramatic.",
        conditional_behaviors=(ConditionalBehavior(condition="angry", guidance=("becomes colder", "does not shout")),),
        example_dialogues=(ExampleDialogue(player="Are you angry?", npc="No. Don't make me reconsider."),),
        never_behaviors=("beg for approval",),
    )

    assert definition.example_dialogues[0].npc == "No. Don't make me reconsider."
    assert definition.conditional_behaviors[0].condition == "angry"


def test_character_definition_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        NPCCharacterDefinition.model_validate({"short_description": "x", "mystery": True})

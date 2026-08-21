from epos.infrastructure.llm.models import LLMTask
from epos.infrastructure.llm.tasks import TASK_PROFILES


def test_reason_npc_profile_treats_character_definition_as_stable_canon() -> None:
    instruction = TASK_PROFILES[LLMTask.REASON_NPC].system_instruction

    assert "character_definition" in instruction
    assert "stable identity and voice canon" in instruction
    assert "never copy them as canned replies" in instruction
    assert "current emotional state" in instruction
    assert "does not replace or rewrite their stable identity" in instruction
    assert "Do not control the player" in instruction
    assert "decide love" in instruction

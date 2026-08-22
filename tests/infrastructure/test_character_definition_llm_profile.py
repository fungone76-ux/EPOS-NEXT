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


def test_narration_profile_keeps_private_npc_evidence_out_of_world_narration() -> None:
    instruction = TASK_PROFILES[LLMTask.GENERATE_NARRATION].system_instruction

    assert "NPC_REACTION evidence may ground only NPCDialogueDraft" in instruction
    assert "same NPC" in instruction
    assert "WorldNarrationDraft" in instruction
    assert "observable, player-declaration, action-result, or check-result evidence" in instruction
    assert "target NPC dialogue must be the first unit" in instruction


def test_narration_profile_forbids_unsupported_autobiographical_claims() -> None:
    instruction = TASK_PROFILES[LLMTask.GENERATE_NARRATION].system_instruction

    assert "rhetorical questions" in instruction
    assert "past conduct" in instruction
    assert "personal history" in instruction
    assert "autobiographical" in instruction
    assert "general principles" in instruction


def test_audit_profile_distinguishes_rhetoric_from_unsupported_facts() -> None:
    instruction = TASK_PROFILES[LLMTask.AUDIT_NARRATION].system_instruction

    assert "rhetorical questions" in instruction
    assert "normative statements" in instruction
    assert "aphorisms" in instruction
    assert "general principles" in instruction
    assert "unsupported_npc_fact" in instruction
    assert "unsupported_world_claim" in instruction
    assert "past conduct" in instruction

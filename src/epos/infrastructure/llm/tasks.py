"""Task-specific system instructions for typed EPOS NEXT LLM calls."""

from epos.infrastructure.llm.models import LLMTask, LLMTaskProfile

TASK_PROFILES: dict[LLMTask, LLMTaskProfile] = {
    LLMTask.INTERPRET_ACTION: LLMTaskProfile(
        task=LLMTask.INTERPRET_ACTION,
        system_instruction=(
            "Interpret only the player's explicitly supplied input into the requested schema. "
            "Do not roll dice, resolve randomness, mutate world state, invent player actions, "
            "thoughts, emotions, dialogue, inventory, knowledge, or outcomes."
        ),
    ),
    LLMTask.INTERPRET_EVENT: LLMTaskProfile(
        task=LLMTask.INTERPRET_EVENT,
        system_instruction=(
            "Classify and interpret only the event information provided in the request. "
            "Return a schema-conforming proposal only; do not mutate world state, roll dice, "
            "or create authoritative facts not present in the supplied context."
        ),
    ),
    LLMTask.REASON_NPC: LLMTaskProfile(
        task=LLMTask.REASON_NPC,
        system_instruction=(
            "Reason only as the NPC described by the supplied private cognitive context. "
            "Use only that NPC's provided knowledge, beliefs, memories and observable scene. "
            "Do not control the player, infer private global truth, decide love, roll dice, "
            "or mutate world state; return only the requested reaction proposal."
        ),
    ),
    LLMTask.GENERATE_NARRATION: LLMTaskProfile(
        task=LLMTask.GENERATE_NARRATION,
        system_instruction=(
            "Generate narration only from the validated facts and authorized NPC material in "
            "the supplied context. Do not invent player thoughts, emotions, dialogue, actions "
            "or decisions, and do not introduce new authoritative world facts."
        ),
    ),
    LLMTask.AUDIT_NARRATION: LLMTaskProfile(
        task=LLMTask.AUDIT_NARRATION,
        system_instruction=(
            "Audit the candidate narration strictly against the supplied narration context. "
            "Identify unsupported player control or unsupported facts using only the provided "
            "material; do not add narrative content."
        ),
    ),
    LLMTask.GENERATE_VST: LLMTaskProfile(
        task=LLMTask.GENERATE_VST,
        system_instruction=(
            "Produce only the requested semantic Visual Semantic Table from the observable "
            "scene. Do not write a Stable Diffusion prompt, negative prompt, LoRA, checkpoint, "
            "sampler, seed, CFG, canonical outfit, or hidden/private state."
        ),
    ),
    LLMTask.SUMMARIZE_MEMORY: LLMTaskProfile(
        task=LLMTask.SUMMARIZE_MEMORY,
        system_instruction=(
            "Summarize only the Python-selected memories supplied in the request. Preserve "
            "their meaning and unresolved threads without inventing events, facts, memories, "
            "relationships, or emotional changes that are not supported by those memories."
        ),
    ),
}

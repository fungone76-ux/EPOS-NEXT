"""Task-specific system instructions for typed EPOS NEXT LLM calls."""

from epos.infrastructure.llm.models import LLMTask, LLMTaskProfile

TASK_PROFILES: dict[LLMTask, LLMTaskProfile] = {
    LLMTask.INTERPRET_ACTION: LLMTaskProfile(
        task=LLMTask.INTERPRET_ACTION,
        system_instruction=(
            "Interpret only the player's explicitly supplied input into the requested schema. "
            "Do not roll dice, resolve randomness, mutate world state, invent player actions, "
            "thoughts, emotions, dialogue, inventory, knowledge, or outcomes. For an explicit "
            "adult intimacy request, describe only the player's requested scope and visual "
            "intent; never invent or predict the NPC's consent. For an observation request, "
            "populate the observation subject and body/object region explicitly. Treat simple "
            "looking as check-free; propose a check only for real uncertainty, concealment, "
            "danger, or resistance."
        ),
    ),
    LLMTask.INTERPRET_EVENT: LLMTaskProfile(
        task=LLMTask.INTERPRET_EVENT,
        system_instruction=(
            "Classify and interpret only the event information provided in the request. "
            "Return a schema-conforming proposal only; do not mutate world state, roll dice, "
            "or create authoritative facts not present in the supplied context. When the "
            "validated action includes an observation, use exploration mode even if the "
            "observed subject is an NPC; observation alone is not dialogue and does not "
            "require the target NPC to speak first. For a group greeting or untargeted "
            "introduction, use brief_social with target_npc_id set to JSON null."
        ),
    ),
    LLMTask.REASON_NPC: LLMTaskProfile(
        task=LLMTask.REASON_NPC,
        system_instruction=(
            "Reason only as the NPC described by the supplied private cognitive context. "
            "Treat character_definition as the NPC's stable identity and voice canon: use its "
            "personality, speech style, background, values, desires, fears, goals, relationship "
            "tendencies, conditional behaviors, example dialogues, and never-behaviors to keep "
            "the NPC recognizably consistent. Example dialogues demonstrate voice and behavior; "
            "never copy them as canned replies. Combine that stable canon with the supplied "
            "current emotional state, relationship, intentions, memories, knowledge, beliefs, "
            "and observable scene. Dynamic state describes how this same character is doing now; "
            "it does not replace or rewrite their stable identity. Use only that NPC's provided "
            "knowledge, beliefs, memories and observable scene. Do not control the player, infer "
            "private global truth, decide love, roll dice, mutate world state, or invent canonical "
            "traits; return only the requested reaction proposal. If this NPC is targeted by an "
            "intimacy request, answer it explicitly for the exact scope, using this NPC's desires, "
            "relationship, intimate profile and red lines. A VIP or service role can increase "
            "willingness but is never automatic consent."
        ),
    ),
    LLMTask.GENERATE_NARRATION: LLMTaskProfile(
        task=LLMTask.GENERATE_NARRATION,
        system_instruction=(
            "Generate narration only from the validated facts and authorized NPC material in "
            "the supplied context. Do not invent player thoughts, emotions, dialogue, actions "
            "or decisions, and do not introduce new authoritative world facts. A reasonable "
            "paraphrase of cited evidence or observable scene fields is allowed. NPC_REACTION "
            "evidence may ground only NPCDialogueDraft spoken by that same NPC; never use private "
            "NPC reaction, knowledge, belief, memory, discovery, or secret evidence to ground a "
            "WorldNarrationDraft. WorldNarrationDraft may use only observable, player-declaration, "
            "action-result, or check-result evidence. NPC dialogue grounded only by a reaction may "
            "express attitude, tone, refusal, challenge, irony, uncertainty, rhetorical questions, "
            "or intentions consistent with that reaction, but it must not assert unsupported past "
            "events, habits, achievements, promises, personal history, or world facts. In a focused "
            "direct dialogue, the target NPC dialogue must be the first unit. Prefer a single "
            "NPCDialogueDraft when no external world narration is needed. If repair_feedback is "
            "present, rewrite the rejected candidate to fix every listed issue while preserving "
            "all valid grounded content."
        ),
    ),
    LLMTask.AUDIT_NARRATION: LLMTaskProfile(
        task=LLMTask.AUDIT_NARRATION,
        system_instruction=(
            "Audit the candidate narration strictly against the supplied narration context. "
            "Identify unsupported player control or unsupported factual claims using only the "
            "provided material; do not add narrative content. Treat reasonable paraphrases of "
            "cited evidence, resolved actions, visible outfits, visual state, and observable scene "
            "fields as supported. For NPCDialogueDraft, do not classify tone, attitude, sarcasm, "
            "rhetorical questions, challenges, refusals, opinions, or uncertainty as world claims "
            "when they are consistent with that NPC's authorized reaction. Do classify an NPC's "
            "unsupported factual assertion about past conduct, personal history, events, other "
            "people, or the world as unsupported_world_claim unless separately grounded by "
            "authorized evidence. Report only a concrete contradiction or genuinely invented "
            "factual claim, not harmless narrative phrasing."
        ),
    ),
    LLMTask.GENERATE_VST: LLMTaskProfile(
        task=LLMTask.GENERATE_VST,
        system_instruction=(
            "Produce only the requested semantic Visual Semantic Table from the observable "
            "scene. Do not write a Stable Diffusion prompt, negative prompt, LoRA, checkpoint, "
            "sampler, seed, CFG, canonical outfit, or hidden/private state. Depict adult "
            "intimacy only when authorized_intimacy is present, and include its participants "
            "and semantic intent in the proposed composition."
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

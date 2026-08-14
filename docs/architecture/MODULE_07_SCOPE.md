# Module 07 — Present NPC Cognition

## Scope

Module 07 gives only NPCs physically present with the player a private cognitive pass. The
pipeline implemented here is: local perception -> semantic memory recall -> private context
assembly -> LLM semantic reaction proposal -> Python validation.

The private context contains only the target NPC's identity, personality, speech style, desires,
goals, fears, emotions, relationship with the player, general bond, NPC-owned adult-intimacy
state toward the player, knowledge, beliefs, false beliefs, discoveries, bounded active memories,
Python-ranked semantic recall, secrets with Python-derived disclosure permissions, red lines,
current intentions, local observable scene, exact player input, validated action, and any already
resolved Python check.

It deliberately does not contain global world truth or private state belonging to another NPC.

## Off-screen rule

If an NPC is not at the player's location, `NPCCognitionService.react` returns without memory
recall and without an LLM call. Module 07 creates no invisible autonomous psychology, dialogue,
intentions, relationships, or memories for off-screen NPCs.

## Secrets and disclosure

The LLM may receive a secret in the NPC's private context so it can react credibly around the
subject. Python separately derives `disclosure_allowed`. Module 07 supports required world flags
and a minimum trust threshold. A reaction requesting disclosure of a locked or unknown secret is
rejected before narration.

## Memory use

Long-term semantic recall is mandatory before present-NPC reasoning. Recalled memories are
included directly in `PrivateCognitiveContext`; the acceptance test fails if recall is performed
but its result is discarded. Core and short-term memory are also included through small,
deterministic caps.

## No raw chain of thought

The reaction contract contains only semantic fields: intent, communication goal, emotional tone,
optional observable-action proposal, targets, memory references, and requested secret disclosures.
Pydantic `extra="forbid"` rejects fields such as `chain_of_thought`, direct state mutations, or
player-state claims.

## Explicit exclusions

Module 07 does not generate final dialogue or narration (Module 08), mutate/commit WorldState
(Module 09), create the final ObservableSceneState (Module 10), or persist a new memory of the
turn. The final `REMEMBER` step must operate on the canonical event that actually happened after
validation/commit; recording a proposed reaction here would risk remembering events that never
became true.

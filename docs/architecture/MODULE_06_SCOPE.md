# Module 06 — Action Interpreter & Check System

## Scope

Module 06 turns free player language into a strict semantic action contract, validates that
proposal against the local scene and the active Worldpack, and resolves authorized d6 checks
with Python-only randomness.

The Action Interpreter context is deliberately local: exact player input, current location,
present NPCs, player-known locations, Worldpack skill definitions, and the player's relevant
skill ratings. It does not receive unrelated private NPC knowledge or the whole WorldState.

## Authority

The LLM may propose intent, targets, movement, outfit requests, skill_id, difficulty, and
semantic stakes. It cannot provide dice or outcomes. Pydantic `extra="forbid"` rejects those
fields. Python validates targets, destinations, skill existence, skill applicability, rating,
and difficulty before any roll.

Worldpacks declare skill applicability through `SkillDefinition.check_intents`; the engine has
no hardcoded skill names. Multiple skills may support the same semantic intent, but the
selected skill must be one of the Worldpack-authorized choices.

For Module 06, a player's rating is read from `PlayerState.stats` using the exact `skill_id` as
the key. Only positive integral values are exposed as dice-pool ratings. This is an explicit
binding convention, not a universal skill catalog baked into the engine.

## D6 baseline and open product decision

The canonical EPOS documents fix a d6 pool, difficulty 1–6, and the four outcomes, but do not
specify the exact mapping from dice to those outcomes. Therefore the mapping is isolated behind
an `OutcomePolicy` Protocol instead of being embedded in the interpreter or Worldpack loader.

The current provisional `D6OutcomePolicy` is explicit and tested:

- each die >= difficulty is one success;
- 2+ successes -> full_success;
- 1 success -> partial_success;
- 0 successes and every die is 1 -> critical_failure;
- any other 0-success roll -> failure.

This baseline can be replaced without changing action interpretation or Worldpack content once
the Product Owner chooses a definitive rule.

## Explicit exclusions

Module 06 does not implement NPC cognition, narration, state mutations, atomic persistence,
post-roll checkpoint/resume, provider-specific OpenAI/Gemini adapters, or fail-forward world
consequences. Those are owned by later modules. In particular, Module 09 will persist/checkpoint
a resolved roll so a crash can never trigger a reroll.

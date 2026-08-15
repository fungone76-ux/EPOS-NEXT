# Module 03 — Adult Intimacy & Sexual Relationship System

Module 03 separates adult sexual dynamics from ordinary relationships and emotional bonds.
It does not itself implement NPC cognition, dialogue generation, memory retrieval, or love
derivation. Module 25 later supplies the separate Python-derived `LovePhase` policy.

Implemented boundaries:

- NPC intimacy is tracked per partner with sexual attraction, desire, arousal, comfort, and tension;
- the engine never creates player desire, arousal, or sexual preference state;
- player and NPC must both be explicitly marked as adult-verified before sexual authorization;
- consent is scoped to a specific intimacy category and the current authoritative turn;
- consent can be declined or withdrawn;
- high attraction, desire, arousal, comfort, or tension never implies consent;
- semantic intimacy events contain meaning and normalized intensity only;
- Python maps semantic events to deterministic NPC intimacy deltas and clamps state to 0..10;
- completed sexual activity can be recorded only from a valid authorization result;
- `BondPhase` is a general emotional bond: none, forming, established, deep;
- a later optional `LovePhase` remains separate from sexual intimacy and general bond depth.

Deliberately excluded:

- automatic or LLM-controlled player desire;
- love or `in_love` derivation inside this module;
- explicit scene narration;
- off-screen NPC sexual cognition;
- persistence/commit orchestration;
- LLM provider calls.

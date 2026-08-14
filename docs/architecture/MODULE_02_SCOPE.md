# Module 02 — Psychology & Relationships

Module 02 adds deterministic psychological consequences while preserving the rule that the LLM interprets and Python governs.

Implemented boundaries:

- semantic `PsychologicalEvent` contains event type, normalized intensity, and context tags only;
- authoritative emotional and relationship deltas are not accepted from the LLM-facing contract;
- Python maps generic semantic event classes to deterministic emotion and relationship effects;
- per-NPC `PsychologyProfile` scales sensitivity without granting authority to the LLM;
- emotional values remain clamped to 0..10;
- relationship dimensions remain independent and clamped to -10..10;
- emotional decay is deterministic and driven by elapsed world-time units supplied by Python;
- zero elapsed time produces no psychological change.

Deliberately excluded from Module 02:

- bond/love derivation;
- memory retrieval or consolidation;
- NPC cognition or dialogue generation;
- WorldState mutation/commit orchestration;
- LLM provider calls;
- off-screen autonomous psychology.

Generic event rules currently cover insult, praise, threat, reassurance, kindness, betrayal, kept/broken promises, humiliation, and support. These are engine-level semantic categories, not Worldpack characters, locations, missions, or other content.

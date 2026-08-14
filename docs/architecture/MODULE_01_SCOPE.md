# Module 01 — Domain & Authoritative World State

Module 01 defines validated persistent state only. It deliberately contains no LLM calls,
no emotional update rules, no relationship mutation engine, no bond/love derivation, and no
memory retrieval behavior.

Implemented state contracts:

- `WorldState` as the authoritative session root;
- `PlayerState` and `NPCState` as persistent entities;
- explicit world truth vs actor knowledge containers;
- bounded emotional and multidimensional relationship state;
- persisted bond phase without derivation logic;
- minimal memory records required by the NPC container;
- authoritative outfit and separate visual state;
- locations, missions, events, threads, skill definitions, narrative/rendering config;
- deterministic outfit layering and canonical NPC lookup.

The behavioral engines that mutate or derive these fields belong to later modules.

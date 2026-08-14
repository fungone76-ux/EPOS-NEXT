# Module 04 — NPC Memory System

## Included

- bounded short-term memory with a default limit of 16 meaningful entries
- separate core and emotional memory layers on `NPCState`
- long-term semantic memory behind the async `MemoryStorePort`
- deterministic bounded recall from player input, scene context, current NPC goals, salience,
  and recency
- archive isolation by NPC
- `SimpleMemoryAdapter` for deterministic tests/local fallback
- `ChromaMemoryAdapter` async boundary that moves synchronous collection operations through
  `asyncio.to_thread`
- fifth-level consolidation capsules
- Python-owned consolidation trigger, source selection, protection rules and provenance
- LLM-facing `MemorySummarizerPort` that can only summarize Python-selected source memories
- raw source memories retained after consolidation

## Protected from ordinary consolidation

- core memories
- explicitly protected memories
- promises
- betrayals
- confessions
- discovered secrets
- irreversible decisions
- relationship milestones

## Explicitly excluded

- concrete OpenAI/Gemini summarizer adapters; provider integration belongs to Module 17
- NPC reasoning/dialogue use of recalled memories; cognition integration belongs to Module 07
- world-state atomic commit orchestration; belongs to Module 09/18
- automatic off-screen cognition or off-screen memory creation
- deletion of raw long-term memories after capsule creation

## Authority rule

Python decides what is remembered, what is protected, what is retrieved, when consolidation
is triggered, and which source memories enter a capsule. The LLM may only return a structured
summary of the selected memories. Python validates it and constructs canonical provenance.

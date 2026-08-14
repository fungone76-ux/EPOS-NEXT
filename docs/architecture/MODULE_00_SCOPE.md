# Module 00 — Foundation / Architecture & Contracts

This milestone intentionally contains no gameplay rules and no Worldpack-specific content.

It establishes:

- typed IDs;
- recursive JSON-safe types with runtime boundary validation;
- foundational error and result contracts;
- clock and RNG abstractions;
- structured logging context;
- async generic Ports for LLM, renderer, state store, memory store, event bus and embeddings.

The Domain must not depend on infrastructure.

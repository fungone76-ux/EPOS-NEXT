# Module 23 — Cache, Logging and Diagnostics

## LLM cache

`SQLiteLLMCache` has two explicit lookup paths:

- exact cache: SHA-256 of namespace plus canonical request JSON;
- semantic cache: cosine similarity over vectors supplied by `TextEmbeddingPort`.

A hash is never described as semantic. Structured cached responses are validated again
against their Pydantic response model before use. Namespaces prevent cross-task/schema reuse.

## Image cache

The image fingerprint includes Canonical VST, complete prompt contract and backend-neutral
render request. Consequently it covers checkpoint, LoRAs, dimensions, sampling settings,
backend payload and seed. Cache availability does not bypass Visual Director,
canonicalization or prompt compilation for a new turn.

## Structured logging and health

Central structlog helpers bind session, turn, phase, NPC, provider and renderer correlation
fields. `RuntimeDiagnosticsService` evaluates LLM and renderer probes independently and
returns typed degraded/down status rather than crashing GUI or health endpoints.

# Module 19 — Turn Result Contract

`TurnResult` is the stable player/API-facing boundary produced from the internal
`TurnOrchestrationResult` by a pure `TurnResultMapper`.

The public result contains:

- session and committed turn number;
- validated narration and NPC dialogue lines;
- no-check, declined, or resolved Python check outcome;
- visual status, prompt contract summary, LoRAs, image and renderer diagnostics;
- typed post-commit issues and memory/checkpoint diagnostic flags.

It deliberately excludes authoritative `WorldState`, private cognition contexts, memories,
secrets and mutation batches. Mapping never invokes interpretation, RNG, cognition,
narration, memory derivation or rendering.

Renderer failure remains a completed narrative turn. It is represented as a failed visual
result with `retry_available=true`, providing the stable handoff to Module 20.

# Module 20 — Render Recovery and Rerender

The visual pipeline persists `PendingRender` after canonicalization/prompt compilation and
before renderer submission. It contains the session/turn, Canonical VST, deterministic prompt
contract, backend-neutral request snapshot and request version.

Failed renders and renderer exceptions leave that record intact. Successful renders remove
it. `RenderRecoveryService.retry(...)` loads the prepared record and calls only a
backend-specific `PendingRenderExecutorPort`; it has no Action Interpreter, RNG, cognition,
narration, mutation or Visual Director dependency.

The JSON adapter stores at most one pending render per session with atomic replacement.
Failed retries remain retryable; successful retries clear only the exact pending turn.

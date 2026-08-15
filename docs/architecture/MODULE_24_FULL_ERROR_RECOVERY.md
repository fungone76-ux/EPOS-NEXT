# Module 24 — Full Error Recovery

EPOS exposes one classified recovery decision for every expected subsystem failure.
`ErrorRecoveryPolicy` is pure: it never retries, mutates state, or hides an exception. It
selects the action that a runtime, GUI, or API may offer.

## Required taxonomy

The stable `epos.application.recovery` boundary exports all required categories:

- configuration and Worldpack validation;
- LLM transport/provider and structured-contract failures;
- state, check, memory, visual-contract, and prompt-compilation failures;
- workflow validation, renderer connection/execution, and persistence failures.

Subsystem errors subclass the closest category. Driver exceptions are translated at their
adapter boundary and retain the original exception as `__cause__`.

## Recovery invariants

- Pre-commit failures never claim that state was preserved.
- Post-commit renderer failures preserve the narrative turn and permit only `retry_image`.
- Image retry uses the persisted canonical VST, prompt contract, and render request; it does
  not replay dice, NPC cognition, narration, memory planning, or state mutation.
- Unexpected exceptions become explicit `report_bug` decisions and post-commit issues.
- No exception is silently swallowed; there is no `except Exception: pass` path.

The debug API returns the stable error code, concrete category, recommended recovery action,
retryability, and committed-state flag. Presentation layers can therefore offer a correct
button without reverse-engineering exception strings.

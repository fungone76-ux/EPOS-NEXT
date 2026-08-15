# Module 25 — Full Acceptance Suite

`tests/acceptance/test_full_acceptance_suite.py` is the consolidated final behavioural
contract. It runs all thirteen required scenarios with deterministic collaborators and a
real in-process HTTP simulation for ComfyUI.

| Scenario | Contract exercised |
| --- | --- |
| A | Brief Victoria greeting, voice ownership, player agency, visual attempt |
| B | Anger 9 and trust 2 alter the same greeting |
| C | Joy 9 and trust 8 produce a distinct warm response |
| D | Attraction 10 alone does not create love |
| E | Long positive history advances bond/love one Python-owned phase at a time |
| F | An old promise is semantically recalled and enters NPC cognition |
| G | Victoria cannot disclose a secret owned only by Luna |
| H | Five off-screen turns do not mutate Victoria's psychology |
| I | Canonicalization discards an outfit invented by RAW VST |
| J | Identical structured visual input produces byte-identical prompt contracts |
| K | RAW VST → canonical VST → Python prompt → workflow → `/prompt` → image |
| L | Renderer outage preserves narration and returns a retryable visual failure |
| M | Rerender uses the saved contract without dice, cognition, or mutations |

## Emergent bond/love hardening

`EmergentBondPolicy` is replaceable Python policy. General `BondPhase` and optional
`LovePhase` stay separate. Each derivation may advance or regress at most one stage.
Progress requires trust, affection, attraction, respect, low fear/resentment, shared core
memories, elapsed turns/days, and an observed meaningful event. Betrayal and severe blockers
apply hysteresis. LLM-proposable mutations still cannot replace `BondState`.

## Integration level

Scenario K uses the real Worldpack loader, observable-scene builder, visual canonicalizer,
prompt compiler, Comfy workflow template/profile builder, HTTP API client, renderer adapter,
atomic diagnostics store, and atomic image store. Only the external ComfyUI process is
replaced by `httpx.MockTransport`, which verifies the actual `/prompt`, `/history`, and
`/view` requests.

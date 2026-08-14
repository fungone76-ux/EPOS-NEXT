# Module 17 — LLM Provider Integration

## Purpose

Module 17 supplies the physical language-model adapters required by the existing EPOS NEXT application services without moving game authority into the provider layer.

The architectural rule remains:

> The LLM interprets, reasons and narrates. Python governs the world.

Application services continue to depend on the generic asynchronous `LLMPort[RequestT, ResponseT]`. OpenAI and Gemini are infrastructure adapters behind that port.

## Boundaries

The provider layer may:

- serialize an already-built Pydantic request;
- send it to a configured language-model provider;
- request structured JSON output;
- parse provider response metadata;
- validate the returned JSON against the requested Pydantic response model;
- retry in one controlled policy layer;
- use a configured secondary provider after primary-provider failure;
- expose a startup diagnostic containing provider/model/status.

The provider layer must not:

- roll dice;
- mutate `WorldState`;
- decide random outcomes;
- invent authoritative inventory, outfit or knowledge;
- decide love or relationship state;
- control player thoughts, emotions, dialogue, actions or decisions;
- bypass application validators;
- create Stable Diffusion prompts;
- pretend a local stub is a configured real LLM.

## Existing application port

Module 17 does not replace the application contract:

```python
class LLMPort(Protocol[LLMRequestT, LLMResponseT]):
    async def invoke(self, request: LLMRequestT) -> LLMResponseT: ...
```

`StructuredLLMPort[RequestT, ResponseT]` is the infrastructure implementation used to satisfy that typed port.

## Task separation

A shared physical provider does not imply a shared semantic task. Each supported task has a distinct `LLMTaskProfile` and system instruction:

- `interpret_action`
- `interpret_event`
- `reason_npc`
- `generate_narration`
- `audit_narration`
- `generate_vst`
- `summarize_memory`

`audit_narration` is included because the existing narration pipeline already performs a separate semantic audit call.

The task profile does not grant authority. It narrows the provider's job to the context and typed response already selected by Python.

## Provider-neutral request

Before contacting a provider, `StructuredLLMPort` creates a strict provider-neutral request containing:

- task id;
- task-specific system instruction;
- serialized Pydantic request JSON;
- response schema name;
- JSON-safe response schema.

The provider backend receives this request and performs exactly one HTTP attempt.

## OpenAI adapter

`OpenAIResponsesBackend` uses the Responses API and requests JSON Schema structured output.

Runtime fields include:

- configured model;
- task-specific `instructions`;
- serialized request as `input`;
- `store = false`;
- JSON Schema response format with strict mode enabled.

The backend extracts assistant `output_text` and returns it to `StructuredLLMPort`; the backend itself does not retry.

## Gemini adapter

`GeminiInteractionsBackend` uses the Gemini Interactions API.

Runtime fields include:

- configured model;
- task-specific `system_instruction`;
- serialized request as `input`;
- `store = false`;
- JSON response format carrying the Pydantic-derived schema.

The backend extracts text from the final model-output step and returns it to `StructuredLLMPort`; the backend itself does not retry.

## Structured validation

Provider output is not authoritative merely because the provider returned valid JSON.

The sequence is:

```text
Pydantic request
    -> provider-neutral structured request
    -> physical provider
    -> provider payload validation
    -> output text
    -> ResponseModel.model_validate_json(...)
    -> typed proposal
    -> existing application/domain validator
```

Malformed provider envelopes fail with a classified contract/provider error. JSON that violates the requested Pydantic response contract also fails and can participate in controlled retry/fallback.

## Retry ownership

There is exactly one retry owner: `StructuredLLMPort`.

```text
StructuredLLMPort
    primary provider attempt 1
    primary provider attempt 2 (policy permitting)
    secondary provider attempt 1
    secondary provider attempt 2 (policy permitting)
    -> classified all-providers-failed error
```

`OpenAIResponsesBackend` and `GeminiInteractionsBackend` never retry internally. This prevents nested retry multiplication and keeps retry behavior testable.

`LLMRetryPolicy.max_attempts_per_provider` defaults to two and is strictly bounded from one to three.

## Provider fallback

`EPOS_LLM_PROVIDER` selects the primary provider.

If the alternate provider also has both its API key and model configured, it becomes the secondary backend. Either direction is supported:

```text
OpenAI -> Gemini fallback
Gemini -> OpenAI fallback
```

Fallback never changes game authority or validation rules; it only changes which physical model is asked to produce the same typed proposal.

## Environment configuration

Supported variables:

```text
EPOS_LLM_PROVIDER=openai|gemini
OPENAI_API_KEY=...
OPENAI_MODEL=...
GEMINI_API_KEY=...
GEMINI_MODEL=...
```

The source code contains no default model name. Missing model configuration therefore cannot silently drift to a hardcoded model.

API keys are never included in startup diagnostics.

## Startup diagnostic

`build_llm_runtime_from_env()` exposes an explicit diagnostic with:

- selected provider;
- selected model;
- `configured` or `unavailable` status;
- optional configured fallback provider;
- human-readable detail.

Examples:

```text
provider=openai | model=<environment value> | status=configured
provider=openai | model=None | status=unavailable | missing OPENAI_API_KEY, OPENAI_MODEL
status=unavailable | EPOS_LLM_PROVIDER is not configured
```

An unsupported provider is reported as unavailable. It is never guessed or mapped to a fake local implementation.

## Memory compatibility

The existing memory application layer uses `MemorySummarizerPort.summarize(...)` instead of the generic `LLMPort.invoke(...)` method name.

`MemorySummarizerLLMAdapter` preserves that application protocol and delegates to:

```text
StructuredLLMPort[MemorySummaryRequest, MemorySummaryDraft]
```

No memory-policy decisions are moved into infrastructure.

## Failure classification

Module 17 distinguishes:

- unavailable configuration;
- transport failure;
- provider HTTP/provider-status failure;
- malformed provider response envelope;
- structured/Pydantic contract violation;
- exhaustion of all configured providers.

The final exhaustion error is explicit and chained from the most recent classified cause. Provider failures are not silently replaced with fabricated local content.

## TDD evidence

The initial RED commit was `f198f21ae669b9f951f54d1cf9a8ee412511ad79`.

Workflow run `31849920181` failed during test collection because `epos.infrastructure.llm` did not yet exist.

During implementation, workflow run `31850096632` reached 255 passing tests and exposed a Pydantic recursive-alias problem in the provider-neutral request model. The contract was corrected rather than bypassing validation.

Workflow run `31850204732` reached 262 passing tests; only Ruff formatting remained.

Workflow run `31850291823` then passed pytest, Ruff and mypy strict together.

Final documented-head evidence is recorded by the last quality-gates run before the Module 17 pull request is marked ready for review.

## Handoff to Module 18

Module 18 should compose one typed `StructuredLLMPort` per application task from a single configured `LLMRuntime`, then inject those ports into the existing Action Interpreter, NPC Cognition, Narration, Visual Director and memory-consolidation services.

Module 18 must not duplicate provider HTTP code, retry policy or structured-response parsing.

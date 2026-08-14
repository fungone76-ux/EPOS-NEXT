# Module 17 — LLM Provider Integration

## Purpose

Module 17 supplies physical language-model adapters behind the existing typed EPOS NEXT application `LLMPort` without moving game authority into infrastructure.

The architectural rule remains:

> The LLM interprets, reasons and narrates. Python governs the world.

Application services remain provider-agnostic. Provider selection, endpoints, model identifiers and secret-variable names are runtime configuration only.

## Boundaries

The provider layer may:

- serialize an already-built Pydantic request;
- send it to a configured provider endpoint;
- request structured JSON output;
- validate the provider envelope;
- validate output against the requested Pydantic response model;
- retry in one controlled policy layer;
- fall back to a configured secondary provider;
- expose provider/model/status diagnostics without secrets.

The provider layer must not:

- roll dice;
- mutate `WorldState`;
- decide random outcomes;
- create authoritative inventory, outfit or knowledge;
- decide love or relationship state;
- control player thoughts, emotions, dialogue, actions or decisions;
- bypass application validators;
- create Stable Diffusion prompts;
- invent a provider, endpoint or model when configuration is missing.

## Existing application port

Module 17 implements rather than replaces the existing boundary:

```python
class LLMPort(Protocol[LLMRequestT, LLMResponseT]):
    async def invoke(self, request: LLMRequestT) -> LLMResponseT: ...
```

`StructuredLLMPort[RequestT, ResponseT]` adapts arbitrary Pydantic request/response pairs to configured physical backends.

## Task separation

One physical model may perform several tasks, but each task has its own `LLMTaskProfile` and system instruction:

- `interpret_action`
- `interpret_event`
- `reason_npc`
- `generate_narration`
- `audit_narration`
- `generate_vst`
- `summarize_memory`

A task profile narrows the provider's job. It never grants state authority.

## Provider-neutral request

Before contacting a backend, `StructuredLLMPort` creates a strict request containing:

- task id;
- task-specific system instruction;
- serialized Pydantic request JSON;
- response schema name;
- JSON-safe Pydantic-derived response schema.

A physical backend performs exactly one HTTP attempt for each call made by `StructuredLLMPort`.

## OpenAI Responses backend

`OpenAIResponsesBackend` is used for runtime entries whose provider is `openai`.

It accepts an injected `base_url`, configured model, API key and timeout. The request is sent to:

```text
{base_url}/responses
```

It requests strict JSON Schema output, sends task-specific `instructions`, serializes the application request as `input`, and sets `store=false`.

The backend itself never retries.

## OpenAI-compatible Chat backend

`OpenAICompatibleChatBackend` supports providers exposed through an OpenAI-compatible Chat Completions API. It is parameterized by the logical provider id, so provider identity remains visible in diagnostics and fallback ordering even though the wire protocol is compatible.

For the canonical environment mapping in this module, a runtime entry whose provider is `gemini` is routed through this backend and calls:

```text
{base_url}/chat/completions
```

The request carries:

- configured model;
- system message from the task profile;
- user message containing the serialized Pydantic request;
- JSON Schema structured response format.

`GeminiInteractionsBackend` remains available as a native direct adapter for explicit use, but it is not selected by the canonical PRIMARY/SECONDARY environment mapping.

## Structured validation

Provider output is never authoritative merely because it is valid JSON.

```text
Pydantic request
    -> provider-neutral structured request
    -> physical backend
    -> provider-envelope validation
    -> output text
    -> ResponseModel.model_validate_json(...)
    -> typed proposal
    -> existing Python application/domain validator
```

Malformed envelopes, invalid JSON or Pydantic contract violations fail as classified LLM errors and may participate in the controlled retry/fallback policy.

## Retry ownership

There is exactly one retry owner: `StructuredLLMPort`.

```text
primary attempt 1
primary attempt 2  (if policy permits)
secondary attempt 1
secondary attempt 2  (if policy permits)
-> all-providers-failed
```

Physical backends never retry internally. This prevents nested retry multiplication.

`LLMRetryPolicy.max_attempts_per_provider` is strictly bounded from one to three.

## Canonical environment contract

Module 17 uses one PRIMARY/SECONDARY configuration scheme:

```text
EPOS_PRIMARY_LLM_PROVIDER=
EPOS_PRIMARY_LLM_BASE_URL=
EPOS_PRIMARY_LLM_MODEL=
EPOS_PRIMARY_LLM_KEY_ENV=

EPOS_SECONDARY_LLM_PROVIDER=
EPOS_SECONDARY_LLM_BASE_URL=
EPOS_SECONDARY_LLM_MODEL=
EPOS_SECONDARY_LLM_KEY_ENV=

EPOS_LLM_FALLBACK_ENABLED=true|false
EPOS_LLM_TIMEOUT_SECONDS=
```

`EPOS_*_LLM_KEY_ENV` contains the **name** of the environment variable holding the secret. The runtime resolves that variable indirectly. This allows secrets to remain outside repository configuration and avoids coupling provider slots to one fixed secret-variable name.

The runtime never synthesizes a model or endpoint. PRIMARY requires provider, base URL, model, key-variable name and the referenced secret to exist.

If PRIMARY is incomplete or invalid, the LLM runtime is explicitly unavailable.

SECONDARY is used only when fallback is enabled and the secondary configuration is complete. A partial secondary configuration does not invalidate a valid primary; the startup diagnostic reports that secondary is unavailable.

`EPOS_LLM_TIMEOUT_SECONDS` is applied to physical provider calls. Invalid, non-positive or excessive timeout configuration makes startup configuration unavailable rather than silently guessing another value.

## Secret handling

Real `.env` files are runtime-only and must not be committed.

The repository `.env.example` contains variable names/placeholders only. API keys are never written to startup diagnostics, provider/model summaries or test fixtures containing production values.

Tests use synthetic keys, models and endpoints.

## Startup diagnostic

`build_llm_runtime_from_env()` exposes:

- primary provider;
- primary model;
- `configured` or `unavailable` status;
- configured fallback provider when available;
- human-readable detail.

It intentionally does **not** expose:

- API key values;
- the resolved secret value;
- request contents.

## Memory compatibility

The memory application layer uses `MemorySummarizerPort.summarize(...)` rather than `LLMPort.invoke(...)`.

`MemorySummarizerLLMAdapter` preserves that application protocol and delegates to:

```text
StructuredLLMPort[MemorySummaryRequest, MemorySummaryDraft]
```

No memory-selection or consolidation policy is moved into infrastructure.

## Failure classification

Module 17 distinguishes:

- unavailable/invalid runtime configuration;
- transport failure;
- provider HTTP/status failure;
- malformed provider response envelope;
- structured/Pydantic contract violation;
- exhaustion of all configured providers.

Provider failure never becomes fabricated local content.

## TDD evidence

The original RED commit was `f198f21ae669b9f951f54d1cf9a8ee412511ad79`; the provider package did not yet exist.

After the initial Module 17 implementation was green, the production runtime environment contract was supplied. A second regression RED was added at commit `8f8619dce23ff2740aa48fb009df34109c25db6a` before adapting production code.

The new regression suite covers:

- PRIMARY/SECONDARY ordering;
- configurable base URLs;
- secret-variable indirection;
- fallback enable/disable;
- timeout validation and propagation;
- OpenAI-compatible Chat Completions structured output;
- absence of secret values from diagnostics.

Final pytest/Ruff/mypy evidence is recorded by the last green quality-gates run before PR #19 is returned to Ready for review.

## Handoff

The Turn Orchestrator should build one typed `StructuredLLMPort` per application task from a single `LLMRuntime`, then inject those ports into Action Interpreter, NPC Cognition, Narration, Visual Director and memory consolidation.

It must not duplicate provider HTTP, retry, fallback or structured-response parsing.

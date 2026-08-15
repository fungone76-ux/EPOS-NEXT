from __future__ import annotations

import json
from typing import Annotated, Literal

import httpx
import pytest
from pydantic import Field, StringConstraints, field_validator

from epos.application.memory import MemorySummaryDraft, MemorySummaryRequest
from epos.domain.base import DomainModel
from epos.domain.ids import EntityId
from epos.infrastructure.llm import (
    TASK_PROFILES,
    GeminiInteractionsBackend,
    LLMContractError,
    LLMError,
    LLMProviderName,
    LLMProviderStatus,
    LLMRetryPolicy,
    LLMTask,
    LLMUnavailableError,
    MemorySummarizerLLMAdapter,
    OpenAIResponsesBackend,
    StructuredLLMPort,
    build_llm_runtime_from_env,
)


class SampleRequest(DomainModel):
    text: str


class SampleResponse(DomainModel):
    answer: str
    score: int = Field(ge=0, le=10)


class SemanticTokenResponse(DomainModel):
    token: str

    @field_validator("token")
    @classmethod
    def require_semantic_token(cls, value: str) -> str:
        if " " in value:
            raise ValueError("token must not contain spaces")
        return value


class _FirstSchemaVariant(DomainModel):
    kind: Literal["first"] = "first"
    value: str


class _SecondSchemaVariant(DomainModel):
    kind: Literal["second"] = "second"
    value: int


_SchemaVariant = Annotated[
    _FirstSchemaVariant | _SecondSchemaVariant,
    Field(discriminator="kind"),
]


class OpenAISchemaSubsetResponse(DomainModel):
    label: str = Field(min_length=1, max_length=32)
    token: Annotated[str, StringConstraints(pattern=r"^[a-z_]+$")]
    variants: tuple[_SchemaVariant, ...] = ()


def _json_response(answer: str = "ok", score: int = 7) -> str:
    return json.dumps({"answer": answer, "score": score})


def _openai_response(text: str) -> dict[str, object]:
    return {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
        "usage": {"input_tokens": 11, "output_tokens": 5, "total_tokens": 16},
    }


def _gemini_response(text: str) -> dict[str, object]:
    return {
        "status": "completed",
        "steps": [
            {"type": "user_input", "status": "done", "content": []},
            {
                "type": "model_output",
                "status": "done",
                "content": [{"type": "text", "text": text}],
            },
        ],
        "usage": {"input_tokens": 13, "output_tokens": 6, "total_tokens": 19},
    }


def _canonical_runtime_env() -> dict[str, str]:
    return {
        "EPOS_PRIMARY_LLM_PROVIDER": "openai",
        "EPOS_PRIMARY_LLM_BASE_URL": "https://openai.example/v1",
        "EPOS_PRIMARY_LLM_MODEL": "openai-model-from-env",
        "EPOS_PRIMARY_LLM_KEY_ENV": "OPENAI_API_KEY",
        "OPENAI_API_KEY": "openai-secret",
        "EPOS_SECONDARY_LLM_PROVIDER": "gemini",
        "EPOS_SECONDARY_LLM_BASE_URL": "https://gemini-compatible.example/v1",
        "EPOS_SECONDARY_LLM_MODEL": "gemini-model-from-env",
        "EPOS_SECONDARY_LLM_KEY_ENV": "GEMINI_API_KEY",
        "GEMINI_API_KEY": "gemini-secret",
        "EPOS_LLM_FALLBACK_ENABLED": "true",
        "EPOS_LLM_TIMEOUT_SECONDS": "180",
    }


def test_task_profiles_are_distinct_and_cover_required_epos_tasks() -> None:
    required = {
        LLMTask.INTERPRET_ACTION,
        LLMTask.INTERPRET_EVENT,
        LLMTask.REASON_NPC,
        LLMTask.GENERATE_NARRATION,
        LLMTask.GENERATE_VST,
        LLMTask.SUMMARIZE_MEMORY,
    }

    assert required.issubset(TASK_PROFILES)
    assert LLMTask.AUDIT_NARRATION in TASK_PROFILES
    assert len({profile.system_instruction for profile in TASK_PROFILES.values()}) == len(
        TASK_PROFILES
    )
    assert "do not roll" in TASK_PROFILES[LLMTask.INTERPRET_ACTION].system_instruction.casefold()
    assert "simple looking as check-free" in TASK_PROFILES[
        LLMTask.INTERPRET_ACTION
    ].system_instruction.casefold()
    focus_instruction = TASK_PROFILES[LLMTask.INTERPRET_EVENT].system_instruction.casefold()
    assert "observation" in focus_instruction
    assert "exploration mode" in focus_instruction
    assert "player" in TASK_PROFILES[LLMTask.REASON_NPC].system_instruction.casefold()
    narration_instruction = TASK_PROFILES[
        LLMTask.GENERATE_NARRATION
    ].system_instruction.casefold()
    assert "repair_feedback" in narration_instruction
    audit_instruction = TASK_PROFILES[LLMTask.AUDIT_NARRATION].system_instruction.casefold()
    assert "reasonable paraphrases" in audit_instruction
    assert "stable diffusion" in TASK_PROFILES[LLMTask.GENERATE_VST].system_instruction.casefold()


def test_runtime_from_env_reports_selected_provider_model_and_fallback_without_secrets() -> None:
    runtime = build_llm_runtime_from_env(_canonical_runtime_env())

    diagnostic = runtime.startup_diagnostic
    assert diagnostic.status is LLMProviderStatus.CONFIGURED
    assert diagnostic.provider is LLMProviderName.OPENAI
    assert diagnostic.model == "openai-model-from-env"
    assert diagnostic.fallback_provider is LLMProviderName.GEMINI
    dumped = diagnostic.model_dump_json()
    assert "openai-secret" not in dumped
    assert "gemini-secret" not in dumped
    assert tuple(backend.model for backend in runtime.backends) == (
        "openai-model-from-env",
        "gemini-model-from-env",
    )


def test_runtime_without_primary_secret_is_explicitly_unavailable() -> None:
    environ = _canonical_runtime_env()
    environ.pop("OPENAI_API_KEY")
    runtime = build_llm_runtime_from_env(environ)

    assert runtime.startup_diagnostic.status is LLMProviderStatus.UNAVAILABLE
    assert runtime.startup_diagnostic.provider is LLMProviderName.OPENAI
    assert runtime.backends == ()
    assert "OPENAI_API_KEY" in runtime.startup_diagnostic.detail
    assert "LocalStub" not in runtime.startup_diagnostic.detail

    with pytest.raises(LLMUnavailableError):
        StructuredLLMPort(
            runtime=runtime,
            task=LLMTask.INTERPRET_ACTION,
            response_model=SampleResponse,
        )


@pytest.mark.asyncio
async def test_openai_responses_backend_uses_structured_output_and_environment_model() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_openai_response(_json_response()))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    backend = OpenAIResponsesBackend(
        api_key="openai-secret",
        model="openai-model-from-env",
        client=client,
    )
    port = StructuredLLMPort(
        backends=(backend,),
        task=LLMTask.INTERPRET_ACTION,
        response_model=SampleResponse,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=1),
    )

    result = await port.invoke(SampleRequest(text="open the door"))
    await client.aclose()

    assert result == SampleResponse(answer="ok", score=7)
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["authorization"] == "Bearer openai-secret"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "openai-model-from-env"
    assert payload["store"] is False
    instructions = payload["instructions"]
    assert isinstance(instructions, str)
    assert instructions.startswith(TASK_PROFILES[LLMTask.INTERPRET_ACTION].system_instruction)
    assert json.loads(str(payload["input"])) == {"text": "open the door"}
    text_config = payload["text"]
    assert isinstance(text_config, dict)
    output_format = text_config["format"]
    assert isinstance(output_format, dict)
    assert output_format["type"] == "json_schema"
    assert output_format["strict"] is True
    schema = output_format["schema"]
    assert isinstance(schema, dict)
    assert set(schema["required"]) == {"answer", "score"}


@pytest.mark.asyncio
async def test_openai_schema_is_rewritten_to_the_supported_strict_subset() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json=_openai_response(
                json.dumps({"label": "ok", "token": "valid_token", "variants": []})
            ),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    port = StructuredLLMPort(
        backends=(OpenAIResponsesBackend(api_key="key", model="gpt-4o-mini", client=client),),
        task=LLMTask.INTERPRET_ACTION,
        response_model=OpenAISchemaSubsetResponse,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=1),
    )

    await port.invoke(SampleRequest(text="probe schema"))
    await client.aclose()

    payload = captured["payload"]
    assert isinstance(payload, dict)
    text_config = payload["text"]
    assert isinstance(text_config, dict)
    output_format = text_config["format"]
    assert isinstance(output_format, dict)
    schema = output_format["schema"]
    assert isinstance(schema, dict)
    serialized_schema = json.dumps(schema)
    assert '"minLength"' not in serialized_schema
    assert '"maxLength"' not in serialized_schema
    assert '"oneOf"' not in serialized_schema
    assert '"discriminator"' not in serialized_schema
    assert '"anyOf"' in serialized_schema
    assert '"pattern"' in serialized_schema


@pytest.mark.asyncio
async def test_openai_http_error_exposes_sanitized_provider_diagnostic() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": "Invalid schema: unsupported keyword minLength",
                    "type": "invalid_request_error",
                    "param": "text.format.schema",
                    "code": "invalid_json_schema",
                    "internal_secret": "must-not-leak",
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    port = StructuredLLMPort(
        backends=(OpenAIResponsesBackend(api_key="key", model="gpt-4o-mini", client=client),),
        task=LLMTask.INTERPRET_ACTION,
        response_model=SampleResponse,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=1),
    )

    with pytest.raises(LLMError) as exc_info:
        await port.invoke(SampleRequest(text="probe error"))
    await client.aclose()

    diagnostic = str(exc_info.value)
    assert "Invalid schema: unsupported keyword minLength" in diagnostic
    assert "type=invalid_request_error" in diagnostic
    assert "param=text.format.schema" in diagnostic
    assert "code=invalid_json_schema" in diagnostic
    assert "must-not-leak" not in diagnostic


@pytest.mark.asyncio
async def test_openai_receives_explicit_contract_guidance_on_first_attempt() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_openai_response(_json_response()))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    port = StructuredLLMPort(
        backends=(OpenAIResponsesBackend(api_key="key", model="gpt-4o-mini", client=client),),
        task=LLMTask.INTERPRET_ACTION,
        response_model=SampleResponse,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=1),
    )

    await port.invoke(SampleRequest(text="look at Luna's feet"))
    await client.aclose()

    payload = captured["payload"]
    assert isinstance(payload, dict)
    instructions = payload["instructions"]
    assert isinstance(instructions, str)
    assert "copy identifiers exactly" in instructions.casefold()
    assert "semantic token" in instructions.casefold()
    assert "strict json schema" in instructions.casefold()


@pytest.mark.asyncio
async def test_openai_semantic_contract_retry_receives_actionable_validation_feedback() -> None:
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert isinstance(payload, dict)
        payloads.append(payload)
        text = (
            json.dumps({"token": "two words"})
            if len(payloads) == 1
            else json.dumps({"token": "two_words"})
        )
        return httpx.Response(200, json=_openai_response(text))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    port = StructuredLLMPort(
        backends=(OpenAIResponsesBackend(api_key="key", model="gpt-4o-mini", client=client),),
        task=LLMTask.REASON_NPC,
        response_model=SemanticTokenResponse,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=2),
    )

    result = await port.invoke(SampleRequest(text="react"))
    await client.aclose()

    assert result.token == "two_words"
    assert len(payloads) == 2
    repair_instructions = payloads[1]["instructions"]
    assert isinstance(repair_instructions, str)
    assert "repair" in repair_instructions.casefold()
    repair_input = json.loads(str(payloads[1]["input"]))
    assert repair_input["original_input_json"] == '{"text":"react"}'
    assert repair_input["invalid_output_json"] == '{"token": "two words"}'
    assert "token must not contain spaces" in repair_input["validation_errors_json"]


@pytest.mark.asyncio
async def test_gemini_interactions_backend_uses_structured_output_and_environment_model() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers.get("x-goog-api-key")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_gemini_response(_json_response("gemini", 8)))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    backend = GeminiInteractionsBackend(
        api_key="gemini-secret",
        model="gemini-model-from-env",
        client=client,
    )
    port = StructuredLLMPort(
        backends=(backend,),
        task=LLMTask.GENERATE_VST,
        response_model=SampleResponse,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=1),
    )

    result = await port.invoke(SampleRequest(text="scene"))
    await client.aclose()

    assert result == SampleResponse(answer="gemini", score=8)
    assert captured["url"] == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert captured["api_key"] == "gemini-secret"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "gemini-model-from-env"
    assert payload["store"] is False
    system_instruction = payload["system_instruction"]
    assert isinstance(system_instruction, str)
    assert system_instruction.startswith(TASK_PROFILES[LLMTask.GENERATE_VST].system_instruction)
    assert json.loads(str(payload["input"])) == {"text": "scene"}
    formats = payload["response_format"]
    assert isinstance(formats, list)
    text_format = formats[0]
    assert isinstance(text_format, dict)
    assert text_format["type"] == "text"
    assert text_format["mime_type"] == "application/json"
    schema = text_format["schema"]
    assert isinstance(schema, dict)
    assert set(schema["required"]) == {"answer", "score"}


@pytest.mark.asyncio
async def test_contract_error_is_retried_only_by_structured_port() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        text = "not-json" if calls == 1 else _json_response("recovered", 6)
        return httpx.Response(200, json=_openai_response(text))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    backend = OpenAIResponsesBackend(api_key="key", model="model", client=client)
    port = StructuredLLMPort(
        backends=(backend,),
        task=LLMTask.REASON_NPC,
        response_model=SampleResponse,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=2),
    )

    result = await port.invoke(SampleRequest(text="react"))
    await client.aclose()

    assert result.answer == "recovered"
    assert calls == 2


@pytest.mark.asyncio
async def test_pydantic_contract_violation_is_classified_and_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        text = _json_response("bad", 99) if calls == 1 else _json_response("valid", 4)
        return httpx.Response(200, json=_openai_response(text))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    backend = OpenAIResponsesBackend(api_key="key", model="model", client=client)
    port = StructuredLLMPort(
        backends=(backend,),
        task=LLMTask.GENERATE_NARRATION,
        response_model=SampleResponse,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=2),
    )

    result = await port.invoke(SampleRequest(text="narrate"))
    await client.aclose()

    assert result == SampleResponse(answer="valid", score=4)
    assert calls == 2


@pytest.mark.asyncio
async def test_primary_transport_failure_falls_back_to_secondary_provider() -> None:
    openai_calls = 0
    gemini_calls = 0

    def openai_handler(request: httpx.Request) -> httpx.Response:
        nonlocal openai_calls
        openai_calls += 1
        raise httpx.ConnectError("offline", request=request)

    def gemini_handler(request: httpx.Request) -> httpx.Response:
        nonlocal gemini_calls
        gemini_calls += 1
        return httpx.Response(200, json=_gemini_response(_json_response("fallback", 9)))

    openai_client = httpx.AsyncClient(transport=httpx.MockTransport(openai_handler))
    gemini_client = httpx.AsyncClient(transport=httpx.MockTransport(gemini_handler))
    openai = OpenAIResponsesBackend(api_key="oa", model="oa-model", client=openai_client)
    gemini = GeminiInteractionsBackend(api_key="gm", model="gm-model", client=gemini_client)
    port = StructuredLLMPort(
        backends=(openai, gemini),
        task=LLMTask.INTERPRET_EVENT,
        response_model=SampleResponse,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=1),
    )

    result = await port.invoke(SampleRequest(text="event"))
    await openai_client.aclose()
    await gemini_client.aclose()

    assert result.answer == "fallback"
    assert openai_calls == 1
    assert gemini_calls == 1


@pytest.mark.asyncio
async def test_rate_limited_primary_falls_back_without_repeating_the_same_429() -> None:
    openai_calls = 0

    def openai_handler(request: httpx.Request) -> httpx.Response:
        nonlocal openai_calls
        openai_calls += 1
        return httpx.Response(429, json={"error": {"message": "quota exceeded"}})

    def gemini_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_gemini_response(_json_response("fallback", 8)))

    openai_client = httpx.AsyncClient(transport=httpx.MockTransport(openai_handler))
    gemini_client = httpx.AsyncClient(transport=httpx.MockTransport(gemini_handler))
    port = StructuredLLMPort(
        backends=(
            OpenAIResponsesBackend(api_key="oa", model="oa-model", client=openai_client),
            GeminiInteractionsBackend(api_key="gm", model="gm-model", client=gemini_client),
        ),
        task=LLMTask.INTERPRET_EVENT,
        response_model=SampleResponse,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=3),
    )

    result = await port.invoke(SampleRequest(text="event"))
    await openai_client.aclose()
    await gemini_client.aclose()

    assert result.answer == "fallback"
    assert openai_calls == 1


@pytest.mark.asyncio
async def test_all_provider_error_names_each_provider_and_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "quota exceeded"}})

    first_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    second_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    port = StructuredLLMPort(
        backends=(
            OpenAIResponsesBackend(api_key="oa", model="oa-model", client=first_client),
            GeminiInteractionsBackend(api_key="gm", model="gm-model", client=second_client),
        ),
        task=LLMTask.REASON_NPC,
        response_model=SampleResponse,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=2),
    )

    with pytest.raises(LLMError) as exc_info:
        await port.invoke(SampleRequest(text="react"))

    await first_client.aclose()
    await second_client.aclose()
    message = str(exc_info.value)
    assert "openai/oa-model" in message
    assert "gemini/gm-model" in message
    assert message.count("HTTP 429") == 2


@pytest.mark.asyncio
async def test_all_provider_failures_raise_one_classified_llm_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    first_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    second_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    first = OpenAIResponsesBackend(api_key="oa", model="oa-model", client=first_client)
    second = GeminiInteractionsBackend(api_key="gm", model="gm-model", client=second_client)
    port = StructuredLLMPort(
        backends=(first, second),
        task=LLMTask.INTERPRET_EVENT,
        response_model=SampleResponse,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=1),
    )

    with pytest.raises(LLMError, match="all configured LLM providers failed"):
        await port.invoke(SampleRequest(text="event"))

    await first_client.aclose()
    await second_client.aclose()


@pytest.mark.asyncio
async def test_malformed_provider_payload_is_not_mistaken_for_valid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "completed", "output": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    backend = OpenAIResponsesBackend(api_key="key", model="model", client=client)
    port = StructuredLLMPort(
        backends=(backend,),
        task=LLMTask.INTERPRET_ACTION,
        response_model=SampleResponse,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=1),
    )

    with pytest.raises(LLMError, match="all configured LLM providers failed") as exc_info:
        await port.invoke(SampleRequest(text="action"))

    await client.aclose()
    assert isinstance(exc_info.value.__cause__, LLMContractError)


class _MemoryPort:
    def __init__(self) -> None:
        self.requests: list[MemorySummaryRequest] = []

    async def invoke(self, request: MemorySummaryRequest) -> MemorySummaryDraft:
        self.requests.append(request)
        return MemorySummaryDraft(summary="capsule", themes=("trust",))


@pytest.mark.asyncio
async def test_memory_summarizer_adapter_preserves_existing_application_protocol() -> None:
    typed_port = _MemoryPort()
    adapter = MemorySummarizerLLMAdapter(typed_port)
    request = MemorySummaryRequest(npc_id=EntityId("victoria"), memories=())

    result = await adapter.summarize(request)

    assert result.summary == "capsule"
    assert typed_port.requests == [request]


def test_runtime_environment_mapping_is_read_only_input() -> None:
    environ = _canonical_runtime_env()

    runtime = build_llm_runtime_from_env(environ)

    assert runtime.startup_diagnostic.provider is LLMProviderName.OPENAI
    assert runtime.startup_diagnostic.model == "openai-model-from-env"
    assert environ["EPOS_PRIMARY_LLM_MODEL"] == "openai-model-from-env"

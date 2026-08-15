"""Single-shot HTTP backends for OpenAI Responses and compatible chat APIs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast

import httpx

from epos.domain.json_types import JSONObject, JSONValue, ensure_json_object
from epos.infrastructure.llm.errors import (
    LLMContractError,
    LLMProviderResponseError,
    LLMTransportError,
)
from epos.infrastructure.llm.models import (
    LLMProviderName,
    ProviderCompletion,
    StructuredLLMRequest,
)

_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_GEMINI_INTERACTIONS_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_MAX_PROVIDER_ERROR_MESSAGE_LENGTH = 500
_MAX_PROVIDER_ERROR_FIELD_LENGTH = 120


class StructuredLLMBackend(Protocol):
    @property
    def provider(self) -> LLMProviderName: ...

    @property
    def model(self) -> str: ...

    @property
    def base_url(self) -> str: ...

    @property
    def timeout_seconds(self) -> float: ...

    async def complete(self, request: StructuredLLMRequest) -> ProviderCompletion: ...


def _normalize_base_url(value: str) -> str:
    result = value.strip().rstrip("/")
    if not result.startswith(("http://", "https://")):
        raise ValueError("LLM base_url must use http:// or https://")
    return result


def _json_payload(response: httpx.Response) -> JSONObject:
    try:
        raw: object = response.json()
    except ValueError as exc:
        raise LLMContractError("LLM provider returned non-JSON response metadata") from exc
    if not isinstance(raw, dict):
        raise LLMContractError("LLM provider response must be a JSON object")
    return ensure_json_object(cast(Mapping[str, object], raw))


def _object(value: JSONValue | None, *, path: str) -> JSONObject:
    if not isinstance(value, dict):
        raise LLMContractError(f"expected JSON object at {path}")
    return value


def _array(value: JSONValue | None, *, path: str) -> list[JSONValue]:
    if not isinstance(value, list):
        raise LLMContractError(f"expected JSON array at {path}")
    return value


def _string(value: JSONValue | None, *, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LLMContractError(f"expected non-empty string at {path}")
    return value


def _optional_non_negative_int(value: JSONValue | None) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _usage(payload: JSONObject) -> tuple[int | None, int | None]:
    usage_value = payload.get("usage")
    if not isinstance(usage_value, dict):
        return None, None
    return (
        _optional_non_negative_int(usage_value.get("input_tokens")),
        _optional_non_negative_int(usage_value.get("output_tokens")),
    )


def _chat_usage(payload: JSONObject) -> tuple[int | None, int | None]:
    usage_value = payload.get("usage")
    if not isinstance(usage_value, dict):
        return None, None
    return (
        _optional_non_negative_int(usage_value.get("prompt_tokens")),
        _optional_non_negative_int(usage_value.get("completion_tokens")),
    )


def _normalize_openai_schema(value: JSONValue) -> JSONValue:
    """Return the Pydantic schema in the strict subset expected by structured output."""
    if isinstance(value, list):
        return [_normalize_openai_schema(item) for item in value]
    if not isinstance(value, dict):
        return value

    result: JSONObject = {}
    for key, item in value.items():
        if key in {"default", "minLength", "maxLength", "discriminator"}:
            continue
        normalized_key = "anyOf" if key == "oneOf" else key
        result[normalized_key] = _normalize_openai_schema(item)

    properties = result.get("properties")
    if isinstance(properties, dict):
        result["required"] = list(properties)
        result["additionalProperties"] = False
    return result


def _sanitized_provider_error(response: httpx.Response) -> str:
    """Extract only documented, non-secret provider error fields."""
    try:
        raw: object = response.json()
    except ValueError:
        return ""
    if not isinstance(raw, dict):
        return ""
    error = raw.get("error")
    if not isinstance(error, dict):
        return ""

    message = error.get("message")
    if not isinstance(message, str):
        message = ""
    message = " ".join(message.split())[:_MAX_PROVIDER_ERROR_MESSAGE_LENGTH]

    fields: list[str] = []
    for key in ("type", "param", "code"):
        value = error.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        sanitized = " ".join(value.split())[:_MAX_PROVIDER_ERROR_FIELD_LENGTH]
        fields.append(f"{key}={sanitized}")

    metadata = f" ({', '.join(fields)})" if fields else ""
    if message:
        return f": {message}{metadata}"
    return metadata


class _HTTPBackend:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        client: httpx.AsyncClient | None,
        timeout_seconds: float,
    ) -> None:
        if not api_key.strip():
            raise ValueError("LLM API key must not be empty")
        if not model.strip():
            raise ValueError("LLM model must not be empty")
        if timeout_seconds <= 0.0:
            raise ValueError("LLM timeout_seconds must be positive")
        self._api_key = api_key
        self._model = model.strip()
        self._base_url = _normalize_base_url(base_url)
        self._client = client
        self._timeout_seconds = timeout_seconds

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    async def _post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: JSONObject,
        provider_label: str,
    ) -> httpx.Response:
        try:
            if self._client is not None:
                response = await self._client.post(url, headers=headers, json=body)
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise LLMTransportError(
                f"{provider_label} request failed: {type(exc).__name__}"
            ) from exc
        if response.status_code >= 400:
            provider_detail = _sanitized_provider_error(response)
            raise LLMProviderResponseError(
                f"{provider_label} request failed with HTTP {response.status_code}"
                f"{provider_detail}",
                http_status=response.status_code,
            )
        return response


class OpenAIResponsesBackend(_HTTPBackend):
    """One HTTP attempt against an OpenAI Responses-compatible endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = _DEFAULT_OPENAI_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            client=client,
            timeout_seconds=timeout_seconds,
        )

    @property
    def provider(self) -> LLMProviderName:
        return LLMProviderName.OPENAI

    async def complete(self, request: StructuredLLMRequest) -> ProviderCompletion:
        strict_schema = _normalize_openai_schema(request.json_schema)
        if not isinstance(strict_schema, dict):
            raise LLMContractError("OpenAI structured output schema must be an object")
        body: JSONObject = {
            "model": self.model,
            "instructions": request.system_instruction,
            "input": request.input_json,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": request.schema_name,
                    "schema": strict_schema,
                    "strict": True,
                }
            },
        }
        response = await self._post(
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            body=body,
            provider_label="OpenAI",
        )
        payload = _json_payload(response)
        if payload.get("status") != "completed":
            raise LLMProviderResponseError("OpenAI response did not complete successfully")
        text = self._extract_text(payload)
        input_tokens, output_tokens = _usage(payload)
        return ProviderCompletion(
            provider=self.provider,
            model=self.model,
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    @staticmethod
    def _extract_text(payload: JSONObject) -> str:
        for item in _array(payload.get("output"), path="$.output"):
            message = _object(item, path="$.output[]")
            if message.get("type") != "message":
                continue
            for content_item in _array(message.get("content"), path="$.output[].content"):
                content = _object(content_item, path="$.output[].content[]")
                if content.get("type") == "output_text":
                    return _string(content.get("text"), path="$.output[].content[].text")
        raise LLMContractError("OpenAI response contained no output_text content")


class OpenAICompatibleChatBackend(_HTTPBackend):
    """Single-shot OpenAI-compatible Chat Completions structured-output backend."""

    def __init__(
        self,
        *,
        provider: LLMProviderName,
        api_key: str,
        model: str,
        base_url: str,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            client=client,
            timeout_seconds=timeout_seconds,
        )
        self._provider = provider

    @property
    def provider(self) -> LLMProviderName:
        return self._provider

    async def complete(self, request: StructuredLLMRequest) -> ProviderCompletion:
        strict_schema = _normalize_openai_schema(request.json_schema)
        if not isinstance(strict_schema, dict):
            raise LLMContractError("OpenAI-compatible schema must be an object")
        body: JSONObject = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_instruction},
                {"role": "user", "content": request.input_json},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "schema": strict_schema,
                    "strict": True,
                },
            },
        }
        response = await self._post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            body=body,
            provider_label=self.provider.value,
        )
        payload = _json_payload(response)
        text = self._extract_text(payload)
        input_tokens, output_tokens = _chat_usage(payload)
        return ProviderCompletion(
            provider=self.provider,
            model=self.model,
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    @staticmethod
    def _extract_text(payload: JSONObject) -> str:
        choices = _array(payload.get("choices"), path="$.choices")
        if not choices:
            raise LLMContractError("OpenAI-compatible response contained no choices")
        choice = _object(choices[0], path="$.choices[0]")
        message = _object(choice.get("message"), path="$.choices[0].message")
        return _string(message.get("content"), path="$.choices[0].message.content")


class GeminiInteractionsBackend(_HTTPBackend):
    """Direct Gemini Interactions backend retained for explicit native use."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = _DEFAULT_GEMINI_INTERACTIONS_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            client=client,
            timeout_seconds=timeout_seconds,
        )

    @property
    def provider(self) -> LLMProviderName:
        return LLMProviderName.GEMINI

    async def complete(self, request: StructuredLLMRequest) -> ProviderCompletion:
        body: JSONObject = {
            "model": self.model,
            "input": request.input_json,
            "system_instruction": request.system_instruction,
            "store": False,
            "response_format": [
                {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": request.json_schema,
                }
            ],
        }
        response = await self._post(
            f"{self.base_url}/interactions",
            headers={
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json",
            },
            body=body,
            provider_label="Gemini",
        )
        payload = _json_payload(response)
        status = payload.get("status")
        if status is not None and status != "completed":
            raise LLMProviderResponseError("Gemini interaction did not complete successfully")
        text = self._extract_text(payload)
        input_tokens, output_tokens = _usage(payload)
        return ProviderCompletion(
            provider=self.provider,
            model=self.model,
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    @staticmethod
    def _extract_text(payload: JSONObject) -> str:
        steps = _array(payload.get("steps"), path="$.steps")
        for item in reversed(steps):
            step = _object(item, path="$.steps[]")
            if step.get("type") != "model_output":
                continue
            for content_item in _array(step.get("content"), path="$.steps[].content"):
                content = _object(content_item, path="$.steps[].content[]")
                if content.get("type") == "text":
                    return _string(content.get("text"), path="$.steps[].content[].text")
        raise LLMContractError("Gemini response contained no model text output")

"""Single-shot HTTP backends for OpenAI Responses and Gemini Interactions."""

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

_OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
_GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


class StructuredLLMBackend(Protocol):
    @property
    def provider(self) -> LLMProviderName: ...

    @property
    def model(self) -> str: ...

    async def complete(self, request: StructuredLLMRequest) -> ProviderCompletion: ...


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


def _normalize_openai_schema(value: JSONValue) -> JSONValue:
    """Return the Pydantic schema in the strict subset expected by Structured Outputs."""
    if isinstance(value, list):
        return [_normalize_openai_schema(item) for item in value]
    if not isinstance(value, dict):
        return value

    result: JSONObject = {}
    for key, item in value.items():
        if key == "default":
            continue
        result[key] = _normalize_openai_schema(item)

    properties = result.get("properties")
    if isinstance(properties, dict):
        result["required"] = list(properties)
        result["additionalProperties"] = False
    return result


class OpenAIResponsesBackend:
    """One HTTP attempt against the OpenAI Responses API; no internal retry."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key must not be empty")
        if not model.strip():
            raise ValueError("OpenAI model must not be empty")
        self._api_key = api_key
        self._model = model.strip()
        self._client = client
        self._timeout_seconds = timeout_seconds

    @property
    def provider(self) -> LLMProviderName:
        return LLMProviderName.OPENAI

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, request: StructuredLLMRequest) -> ProviderCompletion:
        strict_schema = _normalize_openai_schema(request.schema)
        if not isinstance(strict_schema, dict):
            raise LLMContractError("OpenAI structured output schema must be an object")
        body: JSONObject = {
            "model": self._model,
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
            _OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            body=body,
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

    async def _post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: JSONObject,
    ) -> httpx.Response:
        try:
            if self._client is not None:
                response = await self._client.post(url, headers=headers, json=body)
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise LLMTransportError(f"OpenAI request failed: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise LLMProviderResponseError(
                f"OpenAI request failed with HTTP {response.status_code}"
            )
        return response

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


class GeminiInteractionsBackend:
    """One HTTP attempt against Gemini Interactions; no internal retry."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Gemini API key must not be empty")
        if not model.strip():
            raise ValueError("Gemini model must not be empty")
        self._api_key = api_key
        self._model = model.strip()
        self._client = client
        self._timeout_seconds = timeout_seconds

    @property
    def provider(self) -> LLMProviderName:
        return LLMProviderName.GEMINI

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, request: StructuredLLMRequest) -> ProviderCompletion:
        body: JSONObject = {
            "model": self._model,
            "input": request.input_json,
            "system_instruction": request.system_instruction,
            "store": False,
            "response_format": [
                {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": request.schema,
                }
            ],
        }
        response = await self._post(body)
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

    async def _post(self, body: JSONObject) -> httpx.Response:
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        try:
            if self._client is not None:
                response = await self._client.post(
                    _GEMINI_INTERACTIONS_URL,
                    headers=headers,
                    json=body,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(
                        _GEMINI_INTERACTIONS_URL,
                        headers=headers,
                        json=body,
                    )
        except httpx.HTTPError as exc:
            raise LLMTransportError(f"Gemini request failed: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise LLMProviderResponseError(
                f"Gemini request failed with HTTP {response.status_code}"
            )
        return response

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

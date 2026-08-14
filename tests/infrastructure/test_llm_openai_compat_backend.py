from __future__ import annotations

import json

import httpx
import pytest
from pydantic import Field

from epos.domain.base import DomainModel
from epos.infrastructure.llm import (
    LLMProviderName,
    LLMRetryPolicy,
    LLMTask,
    OpenAICompatibleChatBackend,
    StructuredLLMPort,
)


class _Request(DomainModel):
    text: str


class _Response(DomainModel):
    answer: str
    score: int = Field(ge=0, le=10)


@pytest.mark.asyncio
async def test_openai_compatible_gemini_uses_configured_chat_endpoint_and_schema() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"answer": "ok", "score": 8}),
                        }
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    backend = OpenAICompatibleChatBackend(
        provider=LLMProviderName.GEMINI,
        api_key="fake-secret",
        model="fake-gemini-model",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        client=client,
        timeout_seconds=180.0,
    )
    port = StructuredLLMPort(
        backends=(backend,),
        task=LLMTask.GENERATE_VST,
        response_model=_Response,
        retry_policy=LLMRetryPolicy(max_attempts_per_provider=1),
    )

    result = await port.invoke(_Request(text="scene"))
    await client.aclose()

    assert result == _Response(answer="ok", score=8)
    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    )
    assert captured["authorization"] == "Bearer fake-secret"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "fake-gemini-model"
    messages = payload["messages"]
    assert isinstance(messages, list)
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    response_format = payload["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"
    json_schema = response_format["json_schema"]
    assert isinstance(json_schema, dict)
    assert json_schema["strict"] is True
    schema = json_schema["schema"]
    assert isinstance(schema, dict)
    assert set(schema["required"]) == {"answer", "score"}

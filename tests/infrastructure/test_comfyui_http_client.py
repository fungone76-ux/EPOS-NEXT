from __future__ import annotations

import json

import httpx
import pytest

from epos.application.visual.rendering import (
    RendererConnectionError,
    RendererExecutionError,
    RendererProtocolError,
)
from epos.application.visual.workflow import ComfyWorkflowRequest
from epos.infrastructure.rendering.comfy import HttpxComfyApiClient


def _request() -> ComfyWorkflowRequest:
    return ComfyWorkflowRequest(
        prompt={
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            }
        },
        client_id="client-protocol",
    )


def _client(handler: httpx.MockTransport) -> HttpxComfyApiClient:
    return HttpxComfyApiClient(
        endpoint="http://127.0.0.1:8188",
        timeout_seconds=1.0,
        transport=handler,
    )


@pytest.mark.asyncio
async def test_system_stats_uses_canonical_health_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/system_stats"
        return httpx.Response(
            200,
            json={"system": {"comfyui_version": "0.3.50"}, "devices": []},
        )

    payload = await _client(httpx.MockTransport(handler)).get_system_stats()

    assert payload["system"] == {"comfyui_version": "0.3.50"}


@pytest.mark.asyncio
async def test_queue_prompt_sends_exact_workflow_and_client_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/prompt"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload == {
            "prompt": _request().model_dump(mode="json")["prompt"],
            "client_id": "client-protocol",
        }
        return httpx.Response(200, json={"prompt_id": "prompt-http-1", "number": 1})

    prompt_id = await _client(httpx.MockTransport(handler)).queue_prompt(_request())

    assert prompt_id == "prompt-http-1"


@pytest.mark.asyncio
async def test_history_uses_prompt_scoped_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/history/prompt-http-1"
        return httpx.Response(200, json={"prompt-http-1": {"outputs": {}}})

    payload = await _client(httpx.MockTransport(handler)).get_history("prompt-http-1")

    assert "prompt-http-1" in payload


@pytest.mark.asyncio
async def test_view_uses_remote_metadata_only_as_query_parameters() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/view"
        assert request.url.params == {
            "filename": "image.png",
            "subfolder": "session/turn",
            "type": "output",
        }
        return httpx.Response(200, content=b"png-bytes")

    payload = await _client(httpx.MockTransport(handler)).download_image(
        filename="image.png",
        subfolder="session/turn",
        folder_type="output",
    )

    assert payload == b"png-bytes"


@pytest.mark.asyncio
async def test_prompt_4xx_is_execution_error_not_connection_retry() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "invalid prompt"}})

    with pytest.raises(RendererExecutionError, match="HTTP 400"):
        await _client(httpx.MockTransport(handler)).queue_prompt(_request())


@pytest.mark.asyncio
async def test_prompt_5xx_is_connection_class_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="backend unavailable")

    with pytest.raises(RendererConnectionError, match="HTTP 503"):
        await _client(httpx.MockTransport(handler)).queue_prompt(_request())


@pytest.mark.asyncio
async def test_missing_prompt_id_is_protocol_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"number": 1})

    with pytest.raises(RendererProtocolError, match="missing prompt_id"):
        await _client(httpx.MockTransport(handler)).queue_prompt(_request())


@pytest.mark.asyncio
async def test_transport_failure_is_classified_as_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(RendererConnectionError, match="connection failed"):
        await _client(httpx.MockTransport(handler)).get_system_stats()


@pytest.mark.asyncio
async def test_empty_view_payload_is_protocol_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    with pytest.raises(RendererProtocolError, match="empty image payload"):
        await _client(httpx.MockTransport(handler)).download_image(
            filename="image.png",
            subfolder="",
            folder_type="output",
        )

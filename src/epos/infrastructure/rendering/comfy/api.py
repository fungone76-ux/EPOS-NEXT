"""Typed HTTP boundary for ComfyUI's local API."""

from __future__ import annotations

from typing import Protocol

import httpx
from pydantic import JsonValue, TypeAdapter, ValidationError

from epos.application.visual.rendering import (
    RendererConnectionError,
    RendererExecutionError,
    RendererProtocolError,
)
from epos.application.visual.workflow import ComfyWorkflowRequest

_JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


class ComfyApiProtocol(Protocol):
    async def get_system_stats(self) -> dict[str, JsonValue]: ...

    async def queue_prompt(self, request: ComfyWorkflowRequest) -> str: ...

    async def get_history(self, prompt_id: str) -> dict[str, JsonValue]: ...

    async def download_image(
        self,
        *,
        filename: str,
        subfolder: str,
        folder_type: str,
    ) -> bytes: ...


class HttpxComfyApiClient:
    """Async HTTP client for the stable ComfyUI endpoints used by EPOS."""

    def __init__(
        self,
        *,
        endpoint: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def get_system_stats(self) -> dict[str, JsonValue]:
        return await self._json_request("GET", "/system_stats")

    async def queue_prompt(self, request: ComfyWorkflowRequest) -> str:
        response = await self._request(
            "POST",
            "/prompt",
            json_payload=request.model_dump(mode="json"),
        )
        if response.status_code >= 500:
            raise RendererConnectionError(
                f"ComfyUI POST /prompt failed with HTTP {response.status_code}"
            )
        if response.status_code >= 400:
            detail = self._response_detail(response)
            raise RendererExecutionError(
                f"ComfyUI rejected workflow with HTTP {response.status_code}: {detail}"
            )
        payload = self._parse_json_object(response, endpoint="POST /prompt")
        prompt_id = payload.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id.strip():
            raise RendererProtocolError("ComfyUI POST /prompt response missing prompt_id")
        return prompt_id

    async def get_history(self, prompt_id: str) -> dict[str, JsonValue]:
        return await self._json_request("GET", f"/history/{prompt_id}")

    async def download_image(
        self,
        *,
        filename: str,
        subfolder: str,
        folder_type: str,
    ) -> bytes:
        response = await self._request(
            "GET",
            "/view",
            params={
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type,
            },
        )
        if response.status_code >= 400:
            raise RendererConnectionError(
                f"ComfyUI GET /view failed with HTTP {response.status_code}"
            )
        if not response.content:
            raise RendererProtocolError("ComfyUI GET /view returned an empty image payload")
        return bytes(response.content)

    async def _json_request(self, method: str, path: str) -> dict[str, JsonValue]:
        response = await self._request(method, path)
        if response.status_code >= 400:
            raise RendererConnectionError(
                f"ComfyUI {method} {path} failed with HTTP {response.status_code}"
            )
        return self._parse_json_object(response, endpoint=f"{method} {path}")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_payload: object | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                base_url=self._endpoint,
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                return await client.request(
                    method,
                    path,
                    json=json_payload,
                    params=params,
                )
        except httpx.RequestError as exc:
            raise RendererConnectionError(
                f"ComfyUI {method} {path} connection failed: {exc}"
            ) from exc

    @staticmethod
    def _parse_json_object(
        response: httpx.Response,
        *,
        endpoint: str,
    ) -> dict[str, JsonValue]:
        try:
            raw: object = response.json()
            return _JSON_OBJECT.validate_python(raw)
        except (ValueError, ValidationError) as exc:
            raise RendererProtocolError(
                f"ComfyUI {endpoint} returned invalid JSON object"
            ) from exc

    @staticmethod
    def _response_detail(response: httpx.Response) -> str:
        text = response.text.strip()
        if not text:
            return "no response body"
        return text[:500]

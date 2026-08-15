"""Async HTTP boundary for AUTOMATIC1111 / Forge WebUI API."""

from __future__ import annotations

from typing import Protocol

import httpx
from pydantic import JsonValue, TypeAdapter, ValidationError

from epos.application.visual.rendering import (
    RendererConnectionError,
    RendererExecutionError,
    RendererProtocolError,
)
from epos.infrastructure.rendering.a1111.models import A1111RenderRequest
from epos.infrastructure.rendering.a1111.settings import A1111AdapterSettings

_JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


class A1111ApiProtocol(Protocol):
    async def get_options(self) -> dict[str, JsonValue]: ...

    async def txt2img(self, request: A1111RenderRequest) -> bytes: ...


class A1111HTTPClient:
    """Single-attempt HTTP client; POST retry ownership stays outside this boundary."""

    def __init__(
        self,
        *,
        settings: A1111AdapterSettings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings.model_copy(deep=True)
        self._client = client

    async def get_options(self) -> dict[str, JsonValue]:
        response = await self._request("GET", "/sdapi/v1/options")
        if response.status_code >= 400:
            raise RendererConnectionError(
                f"A1111 GET /sdapi/v1/options failed with HTTP {response.status_code}"
            )
        return self._parse_json_object(response, endpoint="GET /sdapi/v1/options")

    async def txt2img(self, request: A1111RenderRequest) -> bytes:
        response = await self._request(
            "POST",
            "/sdapi/v1/txt2img",
            json_payload=request.api_payload(),
        )
        if response.status_code >= 500:
            raise RendererConnectionError(
                f"A1111 POST /sdapi/v1/txt2img failed with HTTP {response.status_code}"
            )
        if response.status_code >= 400:
            detail = response.text.strip()[:500] or "no response body"
            raise RendererExecutionError(
                "A1111 rejected txt2img request with "
                f"HTTP {response.status_code}: {detail}"
            )
        payload = self._parse_json_object(response, endpoint="POST /sdapi/v1/txt2img")
        images = payload.get("images")
        if not isinstance(images, list) or not images:
            raise RendererProtocolError("A1111 txt2img response missing images")
        first = images[0]
        if not isinstance(first, str) or not first.strip():
            raise RendererProtocolError("A1111 txt2img first image is not base64 text")
        return self._decode_base64_image(first)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_payload: object | None = None,
    ) -> httpx.Response:
        try:
            if self._client is not None:
                return await self._client.request(
                    method,
                    f"{self._settings.base_url}{path}",
                    json=json_payload,
                    timeout=self._settings.request_timeout_seconds,
                )
            async with httpx.AsyncClient(
                base_url=self._settings.base_url,
                timeout=self._settings.request_timeout_seconds,
            ) as client:
                return await client.request(method, path, json=json_payload)
        except httpx.RequestError as exc:
            raise RendererConnectionError(
                f"A1111 {method} {path} connection failed: {exc}"
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
                f"A1111 {endpoint} returned invalid JSON object"
            ) from exc

    @staticmethod
    def _decode_base64_image(value: str) -> bytes:
        import base64
        import binascii

        encoded = value.strip()
        if encoded.startswith("data:"):
            marker = encoded.find(",")
            if marker < 0:
                raise RendererProtocolError("A1111 image data URI is malformed")
            encoded = encoded[marker + 1 :]
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise RendererProtocolError("A1111 image payload is invalid base64") from exc
        if not decoded:
            raise RendererProtocolError("A1111 image payload decoded to zero bytes")
        return decoded

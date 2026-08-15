"""RendererPort implementation for AUTOMATIC1111 and Forge."""

from __future__ import annotations

import asyncio
from time import perf_counter

from epos.application.visual.rendering import RendererHealth, RenderResult
from epos.infrastructure.rendering.a1111.api import A1111ApiProtocol
from epos.infrastructure.rendering.a1111.models import A1111RenderRequest
from epos.infrastructure.rendering.a1111.settings import A1111AdapterSettings
from epos.infrastructure.rendering.comfy.image_store import RenderImageStoreProtocol


class A1111ForgeAdapter:
    """Single-submit renderer adapter; ambiguous POST failures are never retried here."""

    def __init__(
        self,
        *,
        settings: A1111AdapterSettings,
        api: A1111ApiProtocol,
        image_store: RenderImageStoreProtocol,
    ) -> None:
        self._settings = settings.model_copy(deep=True)
        self._api = api
        self._image_store = image_store

    async def health_check(self) -> RendererHealth:
        try:
            await self._api.get_options()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return RendererHealth(
                renderer_available=False,
                backend="a1111",
                error=str(exc),
            )
        return RendererHealth(
            renderer_available=True,
            backend="a1111",
            backend_version=None,
            error=None,
        )

    async def render(self, request: A1111RenderRequest) -> RenderResult:
        started = perf_counter()
        try:
            payload = await self._api.txt2img(request)
            image_path = await self._image_store.save(
                prompt_id=request.request_id,
                remote_filename="render.png",
                payload=payload,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return RenderResult(
                status="failed",
                image_path=None,
                backend="a1111",
                prompt_id=request.request_id,
                error=str(exc),
                duration_ms=self._duration_ms(started),
                attempts=1,
            )
        return RenderResult(
            status="success",
            image_path=image_path,
            backend="a1111",
            prompt_id=request.request_id,
            error=None,
            duration_ms=self._duration_ms(started),
            attempts=1,
        )

    @staticmethod
    def _duration_ms(started: float) -> int:
        return max(0, int((perf_counter() - started) * 1000))

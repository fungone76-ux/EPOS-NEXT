"""Async ComfyUI renderer adapter."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping

from epos.application.visual.rendering import (
    RendererConnectionError,
    RendererExecutionError,
    RendererHealth,
    RendererProtocolError,
    RenderResult,
)
from epos.application.visual.workflow import ComfyWorkflowRequest
from epos.domain.errors import PersistenceError
from epos.infrastructure.rendering.comfy.api import ComfyApiProtocol, HttpxComfyApiClient
from epos.infrastructure.rendering.comfy.history import (
    ComfyHistoryInterpreter,
    ComfyImageReference,
)
from epos.infrastructure.rendering.comfy.image_store import (
    AtomicRenderImageStore,
    RenderImageStoreProtocol,
)
from epos.infrastructure.rendering.comfy.settings import ComfyUIAdapterSettings


class ComfyUIAdapter:
    """Render a validated Comfy workflow without knowing game/domain state."""

    backend_name = "comfyui"

    def __init__(
        self,
        *,
        settings: ComfyUIAdapterSettings,
        api: ComfyApiProtocol | None = None,
        image_store: RenderImageStoreProtocol | None = None,
        history: ComfyHistoryInterpreter | None = None,
    ) -> None:
        self._settings = settings
        self._api = api or HttpxComfyApiClient(
            endpoint=settings.endpoint,
            timeout_seconds=settings.request_timeout_seconds,
        )
        self._image_store = image_store or AtomicRenderImageStore(settings.output_directory)
        self._history = history or ComfyHistoryInterpreter()

    async def health_check(self) -> RendererHealth:
        try:
            stats = await self._api.get_system_stats()
            version = self._backend_version(stats)
            return RendererHealth(
                renderer_available=True,
                backend=self.backend_name,
                backend_version=version,
                error=None,
            )
        except (RendererConnectionError, RendererProtocolError, RendererExecutionError) as exc:
            return RendererHealth(
                renderer_available=False,
                backend=self.backend_name,
                backend_version=None,
                error=str(exc),
            )

    async def render(self, request: ComfyWorkflowRequest) -> RenderResult:
        started = time.perf_counter()
        prompt_id: str | None = None
        attempts = 0

        for attempt in range(1, self._settings.max_attempts + 1):
            attempts = attempt
            try:
                prompt_id = await self._api.queue_prompt(request)
                break
            except RendererConnectionError as exc:
                if attempt >= self._settings.max_attempts:
                    return self._failed(
                        started=started,
                        prompt_id=None,
                        attempts=attempts,
                        error=str(exc),
                    )
                if self._settings.retry_delay_seconds > 0:
                    await asyncio.sleep(self._settings.retry_delay_seconds)
            except (RendererExecutionError, RendererProtocolError) as exc:
                return self._failed(
                    started=started,
                    prompt_id=None,
                    attempts=attempts,
                    error=str(exc),
                )

        if prompt_id is None:
            return self._failed(
                started=started,
                prompt_id=None,
                attempts=max(1, attempts),
                error="ComfyUI did not return a prompt_id",
            )

        try:
            image = await self._wait_for_output(prompt_id)
            payload = await self._api.download_image(
                filename=image.filename,
                subfolder=image.subfolder,
                folder_type=image.folder_type,
            )
            image_path = await self._image_store.save(
                prompt_id=prompt_id,
                remote_filename=image.filename,
                payload=payload,
            )
        except (
            RendererConnectionError,
            RendererExecutionError,
            RendererProtocolError,
            PersistenceError,
        ) as exc:
            return self._failed(
                started=started,
                prompt_id=prompt_id,
                attempts=attempts,
                error=str(exc),
            )

        return RenderResult(
            status="success",
            image_path=image_path,
            backend=self.backend_name,
            prompt_id=prompt_id,
            error=None,
            duration_ms=self._duration_ms(started),
            attempts=attempts,
        )

    async def _wait_for_output(self, prompt_id: str) -> ComfyImageReference:
        deadline = time.perf_counter() + self._settings.render_timeout_seconds
        while True:
            payload = await self._api.get_history(prompt_id)
            inspection = self._history.inspect(payload, prompt_id=prompt_id)
            if inspection.state == "success":
                if inspection.image is None:
                    raise RendererProtocolError(
                        "ComfyUI history reported success without image metadata"
                    )
                return inspection.image

            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise RendererExecutionError(
                    f"ComfyUI render timeout after "
                    f"{self._settings.render_timeout_seconds:g} seconds"
                )
            await asyncio.sleep(min(self._settings.poll_interval_seconds, remaining))

    @staticmethod
    def _backend_version(stats: Mapping[str, object]) -> str | None:
        system = stats.get("system")
        if not isinstance(system, dict):
            return None
        version = system.get("comfyui_version")
        if isinstance(version, str) and version.strip():
            return version
        return None

    def _failed(
        self,
        *,
        started: float,
        prompt_id: str | None,
        attempts: int,
        error: str,
    ) -> RenderResult:
        return RenderResult(
            status="failed",
            image_path=None,
            backend=self.backend_name,
            prompt_id=prompt_id,
            error=error,
            duration_ms=self._duration_ms(started),
            attempts=attempts,
        )

    @staticmethod
    def _duration_ms(started: float) -> int:
        return max(0, round((time.perf_counter() - started) * 1000))

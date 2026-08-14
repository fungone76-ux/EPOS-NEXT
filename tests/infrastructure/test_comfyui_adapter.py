from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import JsonValue, ValidationError

from epos.application.visual.rendering import RendererConnectionError
from epos.application.visual.workflow import ComfyWorkflowRequest
from epos.infrastructure.rendering.comfy import (
    AtomicRenderImageStore,
    ComfyUIAdapter,
    ComfyUIAdapterSettings,
)


class FakeComfyApi:
    def __init__(self) -> None:
        self.system_stats: dict[str, JsonValue] = {
            "system": {"comfyui_version": "0.3.50"},
            "devices": [],
        }
        self.queue_outcomes: list[str | Exception] = ["prompt-1"]
        self.history_outcomes: list[dict[str, JsonValue] | Exception] = []
        self.download_outcomes: list[bytes | Exception] = [b"fake-png-bytes"]
        self.queue_calls = 0
        self.history_calls = 0
        self.download_calls = 0
        self.last_request: ComfyWorkflowRequest | None = None
        self.last_download: tuple[str, str, str] | None = None

    async def get_system_stats(self) -> dict[str, JsonValue]:
        return self.system_stats

    async def queue_prompt(self, request: ComfyWorkflowRequest) -> str:
        self.queue_calls += 1
        self.last_request = request
        outcome = self.queue_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def get_history(self, prompt_id: str) -> dict[str, JsonValue]:
        self.history_calls += 1
        if not self.history_outcomes:
            return {}
        outcome = self.history_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def download_image(
        self,
        *,
        filename: str,
        subfolder: str,
        folder_type: str,
    ) -> bytes:
        self.download_calls += 1
        self.last_download = (filename, subfolder, folder_type)
        outcome = self.download_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _request() -> ComfyWorkflowRequest:
    return ComfyWorkflowRequest(
        prompt={
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            }
        },
        client_id="client-1",
    )


def _success_history(prompt_id: str = "prompt-1") -> dict[str, JsonValue]:
    return {
        prompt_id: {
            "outputs": {
                "9": {
                    "images": [
                        {
                            "filename": "Luna_ComfyUI_00001_.png",
                            "subfolder": "",
                            "type": "output",
                        }
                    ]
                }
            },
            "status": {
                "status_str": "success",
                "completed": True,
                "messages": [],
            },
        }
    }


def _settings(tmp_path: Path, **overrides: object) -> ComfyUIAdapterSettings:
    values: dict[str, object] = {
        "endpoint": "http://127.0.0.1:8188",
        "ws_endpoint": "ws://127.0.0.1:8188/ws",
        "output_directory": tmp_path,
        "request_timeout_seconds": 1.0,
        "render_timeout_seconds": 0.03,
        "poll_interval_seconds": 0.001,
        "retry_delay_seconds": 0.0,
        "max_attempts": 3,
    }
    values.update(overrides)
    return ComfyUIAdapterSettings.model_validate(values)


def test_settings_reject_more_than_three_total_attempts(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="less than or equal to 3"):
        _settings(tmp_path, max_attempts=4)


def test_settings_from_env_uses_required_renderer_variables(tmp_path: Path) -> None:
    environ: Mapping[str, str] = {
        "EPOS_RENDER_MODE": "comfyui",
        "EPOS_COMFYUI_ENDPOINT": "http://10.0.0.2:8188",
        "EPOS_COMFYUI_WS_ENDPOINT": "ws://10.0.0.2:8188/ws",
    }

    settings = ComfyUIAdapterSettings.from_env(
        output_directory=tmp_path,
        environ=environ,
    )

    assert settings.endpoint == "http://10.0.0.2:8188"
    assert settings.ws_endpoint == "ws://10.0.0.2:8188/ws"


@pytest.mark.asyncio
async def test_health_check_reports_backend_version(tmp_path: Path) -> None:
    api = FakeComfyApi()
    adapter = ComfyUIAdapter(
        settings=_settings(tmp_path),
        api=api,
        image_store=AtomicRenderImageStore(tmp_path),
    )

    health = await adapter.health_check()

    assert health.renderer_available is True
    assert health.backend == "comfyui"
    assert health.backend_version == "0.3.50"
    assert health.error is None


@pytest.mark.asyncio
async def test_health_check_returns_real_connection_error(tmp_path: Path) -> None:
    class OfflineApi(FakeComfyApi):
        async def get_system_stats(self) -> dict[str, JsonValue]:
            raise RendererConnectionError("connection refused 127.0.0.1:8188")

    adapter = ComfyUIAdapter(
        settings=_settings(tmp_path),
        api=OfflineApi(),
        image_store=AtomicRenderImageStore(tmp_path),
    )

    health = await adapter.health_check()

    assert health.renderer_available is False
    assert health.backend_version is None
    assert "connection refused" in (health.error or "")


@pytest.mark.asyncio
async def test_render_queues_polls_downloads_and_atomically_saves_output(
    tmp_path: Path,
) -> None:
    api = FakeComfyApi()
    api.history_outcomes = [{}, _success_history()]
    adapter = ComfyUIAdapter(
        settings=_settings(tmp_path),
        api=api,
        image_store=AtomicRenderImageStore(tmp_path),
    )

    result = await adapter.render(_request())

    assert result.status == "success"
    assert result.prompt_id == "prompt-1"
    assert result.attempts == 1
    assert result.error is None
    assert result.image_path is not None
    image_path = Path(result.image_path)
    assert image_path.parent == tmp_path
    assert image_path.read_bytes() == b"fake-png-bytes"
    assert not tuple(tmp_path.glob("*.tmp"))
    assert api.queue_calls == 1
    assert api.history_calls == 2
    assert api.download_calls == 1
    assert api.last_download == ("Luna_ComfyUI_00001_.png", "", "output")


@pytest.mark.asyncio
async def test_render_surfaces_comfy_execution_error_with_prompt_id(
    tmp_path: Path,
) -> None:
    api = FakeComfyApi()
    api.history_outcomes = [
        {
            "prompt-1": {
                "outputs": {},
                "status": {
                    "status_str": "error",
                    "completed": True,
                    "messages": [
                        [
                            "execution_error",
                            {
                                "node_id": "4",
                                "node_type": "SamplerCustom",
                                "exception_type": "RuntimeError",
                                "exception_message": "CUDA out of memory",
                            },
                        ]
                    ],
                },
            }
        }
    ]
    adapter = ComfyUIAdapter(
        settings=_settings(tmp_path),
        api=api,
        image_store=AtomicRenderImageStore(tmp_path),
    )

    result = await adapter.render(_request())

    assert result.status == "failed"
    assert result.prompt_id == "prompt-1"
    assert "CUDA out of memory" in (result.error or "")
    assert "SamplerCustom" in (result.error or "")
    assert api.queue_calls == 1
    assert api.download_calls == 0


@pytest.mark.asyncio
async def test_render_timeout_preserves_accepted_prompt_id(tmp_path: Path) -> None:
    api = FakeComfyApi()
    adapter = ComfyUIAdapter(
        settings=_settings(tmp_path, render_timeout_seconds=0.005),
        api=api,
        image_store=AtomicRenderImageStore(tmp_path),
    )

    result = await adapter.render(_request())

    assert result.status == "failed"
    assert result.prompt_id == "prompt-1"
    assert "timeout" in (result.error or "").lower()
    assert api.queue_calls == 1


@pytest.mark.asyncio
async def test_submission_connection_failures_retry_at_most_three_times(
    tmp_path: Path,
) -> None:
    api = FakeComfyApi()
    api.queue_outcomes = [
        RendererConnectionError("offline-1"),
        RendererConnectionError("offline-2"),
        "prompt-1",
    ]
    api.history_outcomes = [_success_history()]
    adapter = ComfyUIAdapter(
        settings=_settings(tmp_path, max_attempts=3),
        api=api,
        image_store=AtomicRenderImageStore(tmp_path),
    )

    result = await adapter.render(_request())

    assert result.status == "success"
    assert result.attempts == 3
    assert api.queue_calls == 3


@pytest.mark.asyncio
async def test_no_automatic_resubmission_after_prompt_was_accepted(
    tmp_path: Path,
) -> None:
    api = FakeComfyApi()
    api.queue_outcomes = ["prompt-accepted", "must-not-be-used"]
    api.history_outcomes = [RendererConnectionError("history disconnected")]
    adapter = ComfyUIAdapter(
        settings=_settings(tmp_path, max_attempts=3),
        api=api,
        image_store=AtomicRenderImageStore(tmp_path),
    )

    result = await adapter.render(_request())

    assert result.status == "failed"
    assert result.prompt_id == "prompt-accepted"
    assert "history disconnected" in (result.error or "")
    assert result.attempts == 1
    assert api.queue_calls == 1


@pytest.mark.asyncio
async def test_completed_job_without_output_image_fails_readably(tmp_path: Path) -> None:
    api = FakeComfyApi()
    api.history_outcomes = [
        {
            "prompt-1": {
                "outputs": {"9": {"images": []}},
                "status": {
                    "status_str": "success",
                    "completed": True,
                    "messages": [],
                },
            }
        }
    ]
    adapter = ComfyUIAdapter(
        settings=_settings(tmp_path),
        api=api,
        image_store=AtomicRenderImageStore(tmp_path),
    )

    result = await adapter.render(_request())

    assert result.status == "failed"
    assert "output image" in (result.error or "")


@pytest.mark.asyncio
async def test_server_filename_cannot_escape_local_render_directory(tmp_path: Path) -> None:
    api = FakeComfyApi()
    api.history_outcomes = [
        {
            "prompt-1": {
                "outputs": {
                    "9": {
                        "images": [
                            {
                                "filename": "../../escape.png",
                                "subfolder": "../../server-side-only",
                                "type": "output",
                            }
                        ]
                    }
                },
                "status": {
                    "status_str": "success",
                    "completed": True,
                    "messages": [],
                },
            }
        }
    ]
    adapter = ComfyUIAdapter(
        settings=_settings(tmp_path),
        api=api,
        image_store=AtomicRenderImageStore(tmp_path),
    )

    result = await adapter.render(_request())

    assert result.status == "success"
    assert result.image_path is not None
    assert Path(result.image_path).parent == tmp_path
    assert not (tmp_path.parent / "escape.png").exists()

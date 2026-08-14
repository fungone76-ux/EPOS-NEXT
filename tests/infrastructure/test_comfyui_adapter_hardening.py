from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import JsonValue

from epos.application.visual.workflow import ComfyWorkflowRequest
from epos.domain.errors import ConfigurationError, PersistenceError
from epos.infrastructure.rendering.comfy import ComfyUIAdapter, ComfyUIAdapterSettings
from epos.infrastructure.rendering.comfy.history import ComfyHistoryInterpreter


class CompletedApi:
    async def get_system_stats(self) -> dict[str, JsonValue]:
        return {"system": {"comfyui_version": "test"}}

    async def queue_prompt(self, request: ComfyWorkflowRequest) -> str:
        assert request.client_id == "client-hardening"
        return "prompt-hardening"

    async def get_history(self, prompt_id: str) -> dict[str, JsonValue]:
        return {
            prompt_id: {
                "outputs": {
                    "9": {
                        "images": [
                            {
                                "filename": "final.png",
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

    async def download_image(
        self,
        *,
        filename: str,
        subfolder: str,
        folder_type: str,
    ) -> bytes:
        assert filename == "final.png"
        assert subfolder == ""
        assert folder_type == "output"
        return b"image"


class BrokenStore:
    async def save(
        self,
        *,
        prompt_id: str,
        remote_filename: str,
        payload: bytes,
    ) -> str:
        raise PersistenceError("disk full")


def _request() -> ComfyWorkflowRequest:
    return ComfyWorkflowRequest(
        prompt={
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            }
        },
        client_id="client-hardening",
    )


def _settings(tmp_path: Path) -> ComfyUIAdapterSettings:
    return ComfyUIAdapterSettings(
        endpoint="http://127.0.0.1:8188",
        output_directory=tmp_path,
        request_timeout_seconds=1.0,
        render_timeout_seconds=0.1,
        poll_interval_seconds=0.001,
        retry_delay_seconds=0.0,
        max_attempts=1,
    )


def test_history_never_uses_temp_preview_as_final_output() -> None:
    payload: dict[str, JsonValue] = {
        "prompt-1": {
            "outputs": {
                "8": {
                    "images": [
                        {
                            "filename": "preview.png",
                            "subfolder": "",
                            "type": "temp",
                        }
                    ]
                },
                "9": {
                    "images": [
                        {
                            "filename": "final.png",
                            "subfolder": "",
                            "type": "output",
                        }
                    ]
                },
            },
            "status": {
                "status_str": "success",
                "completed": True,
                "messages": [],
            },
        }
    }

    result = ComfyHistoryInterpreter().inspect(payload, prompt_id="prompt-1")

    assert result.image is not None
    assert result.image.filename == "final.png"
    assert result.image.folder_type == "output"


@pytest.mark.asyncio
async def test_atomic_store_failure_becomes_failed_render_result(tmp_path: Path) -> None:
    adapter = ComfyUIAdapter(
        settings=_settings(tmp_path),
        api=CompletedApi(),
        image_store=BrokenStore(),
    )

    result = await adapter.render(_request())

    assert result.status == "failed"
    assert result.prompt_id == "prompt-hardening"
    assert result.image_path is None
    assert "disk full" in (result.error or "")


def test_settings_reject_non_comfy_render_mode(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="must be comfyui"):
        ComfyUIAdapterSettings.from_env(
            output_directory=tmp_path,
            environ={
                "EPOS_RENDER_MODE": "disabled",
                "EPOS_COMFYUI_ENDPOINT": "http://127.0.0.1:8188",
            },
        )

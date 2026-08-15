from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import pytest

from epos.application.visual.canonical import ResolvedLora
from epos.application.visual.prompt import RenderPromptContract
from epos.domain.errors import ConfigurationError
from epos.domain.ids import EntityId
from epos.infrastructure.rendering.a1111 import (
    A1111AdapterSettings,
    A1111ForgeAdapter,
    A1111HTTPClient,
    A1111LoraWeightRule,
    A1111RenderProfile,
    A1111RenderRequestBuilder,
)
from epos.infrastructure.rendering.comfy.image_store import AtomicRenderImageStore


def _contract(*, with_lora: bool = False) -> RenderPromptContract:
    loras = ()
    if with_lora:
        loras = (
            ResolvedLora(
                entity_id=EntityId("victoria"),
                alias="victoria_identity",
                filename="victoria_identity.safetensors",
            ),
        )
    return RenderPromptContract(
        positive_prompt="cinematic realism, victoria at the pool",
        negative_prompt="lowres, bad anatomy",
        loras=loras,
        checkpoint="comfy-only-model.safetensors",
        width=896,
        height=1152,
        sampler="DPM++ 2M",
        scheduler="Karras",
        steps=28,
        cfg=6.5,
    )


def _settings(tmp_path: Path) -> A1111AdapterSettings:
    return A1111AdapterSettings(
        base_url="http://127.0.0.1:7860",
        checkpoint="forge-runtime-model.safetensors",
        output_directory=tmp_path,
        request_timeout_seconds=180.0,
    )


def test_a1111_settings_follow_runtime_env_contract(tmp_path: Path) -> None:
    settings = A1111AdapterSettings.from_env(
        output_directory=tmp_path,
        environ={
            "EPOS_RENDER_MODE": "a1111",
            "A1111_BASE_URL": "http://127.0.0.1:7860/",
            "A1111_CHECKPOINT": "runtime-model.safetensors",
        },
    )

    assert settings.base_url == "http://127.0.0.1:7860"
    assert settings.checkpoint == "runtime-model.safetensors"

    with pytest.raises(ConfigurationError, match="EPOS_RENDER_MODE"):
        A1111AdapterSettings.from_env(
            output_directory=tmp_path,
            environ={
                "EPOS_RENDER_MODE": "comfyui",
                "A1111_BASE_URL": "http://127.0.0.1:7860",
                "A1111_CHECKPOINT": "runtime-model.safetensors",
            },
        )


def test_request_builder_uses_runtime_checkpoint_and_backend_lora_layer(tmp_path: Path) -> None:
    builder = A1111RenderRequestBuilder(
        settings=_settings(tmp_path),
        profile=A1111RenderProfile(
            default_lora_weight=0.8,
            lora_weights=(
                A1111LoraWeightRule(alias="victoria_identity", weight=0.65),
            ),
        ),
    )

    built = builder.build(_contract(with_lora=True), seed=123456789)
    request = built.request

    assert request.prompt == (
        "cinematic realism, victoria at the pool, <lora:victoria_identity:0.65>"
    )
    assert request.negative_prompt == "lowres, bad anatomy"
    assert request.seed == 123456789
    assert request.width == 896
    assert request.height == 1152
    assert request.sampler_name == "DPM++ 2M"
    assert request.scheduler == "Karras"
    assert request.steps == 28
    assert request.cfg_scale == 6.5
    assert request.override_settings == {
        "sd_model_checkpoint": "forge-runtime-model.safetensors"
    }
    assert request.override_settings_restore_afterwards is True
    assert "comfy-only-model.safetensors" not in request.model_dump_json()
    assert built.snapshot.backend == "a1111"
    assert built.snapshot.request_id.startswith("a1111-")

    repeated = builder.build(_contract(with_lora=True), seed=123456789)
    assert repeated.snapshot.request_id == built.snapshot.request_id


def test_request_builder_rejects_duplicate_lora_weight_aliases(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicate A1111 LoRA weight alias"):
        A1111RenderProfile(
            lora_weights=(
                A1111LoraWeightRule(alias="victoria_identity", weight=0.5),
                A1111LoraWeightRule(alias="victoria_identity", weight=0.7),
            )
        )


@pytest.mark.asyncio
async def test_a1111_adapter_posts_txt2img_decodes_and_atomically_saves_image(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    png = b"\x89PNG\r\n\x1a\nrendered-image"

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content)
        if request.method == "GET":
            return httpx.Response(200, json={"sd_model_checkpoint": "runtime-model"})
        return httpx.Response(
            200,
            json={
                "images": [base64.b64encode(png).decode("ascii")],
                "parameters": {},
                "info": "{}",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = _settings(tmp_path)
    api = A1111HTTPClient(settings=settings, client=client)
    adapter = A1111ForgeAdapter(
        settings=settings,
        api=api,
        image_store=AtomicRenderImageStore(tmp_path),
    )
    built = A1111RenderRequestBuilder(
        settings=settings,
        profile=A1111RenderProfile(default_lora_weight=0.8),
    ).build(_contract(), seed=42)

    health = await adapter.health_check()
    result = await adapter.render(built.request)
    await client.aclose()

    assert health.renderer_available is True
    assert health.backend == "a1111"
    assert result.status == "success"
    assert result.backend == "a1111"
    assert result.prompt_id == built.request.request_id
    assert result.attempts == 1
    assert result.image_path is not None
    assert Path(result.image_path).read_bytes() == png
    assert captured["method"] == "POST"
    assert captured["url"] == "http://127.0.0.1:7860/sdapi/v1/txt2img"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["seed"] == 42
    assert payload["override_settings"] == {
        "sd_model_checkpoint": "forge-runtime-model.safetensors"
    }


@pytest.mark.asyncio
async def test_a1111_render_does_not_retry_ambiguous_transport_failure(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadError("connection lost after submit", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = _settings(tmp_path)
    adapter = A1111ForgeAdapter(
        settings=settings,
        api=A1111HTTPClient(settings=settings, client=client),
        image_store=AtomicRenderImageStore(tmp_path),
    )
    built = A1111RenderRequestBuilder(
        settings=settings,
        profile=A1111RenderProfile(),
    ).build(_contract(), seed=7)

    result = await adapter.render(built.request)
    await client.aclose()

    assert calls == 1
    assert result.status == "failed"
    assert result.prompt_id == built.request.request_id
    assert result.attempts == 1
    assert result.image_path is None
    assert result.error is not None


@pytest.mark.asyncio
async def test_a1111_empty_or_invalid_base64_response_is_failed_result(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"images": ["%%%"], "parameters": {}, "info": "{}"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = _settings(tmp_path)
    adapter = A1111ForgeAdapter(
        settings=settings,
        api=A1111HTTPClient(settings=settings, client=client),
        image_store=AtomicRenderImageStore(tmp_path),
    )
    built = A1111RenderRequestBuilder(
        settings=settings,
        profile=A1111RenderProfile(),
    ).build(_contract(), seed=9)

    result = await adapter.render(built.request)
    await client.aclose()

    assert result.status == "failed"
    assert result.prompt_id == built.request.request_id
    assert result.image_path is None
    assert result.error is not None

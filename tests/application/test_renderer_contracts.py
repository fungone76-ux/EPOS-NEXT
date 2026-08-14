from __future__ import annotations

import pytest
from pydantic import ValidationError

from epos.application.visual.rendering import RendererHealth, RenderResult


def test_success_render_result_requires_image_and_prompt_id() -> None:
    result = RenderResult(
        status="success",
        image_path="renders/prompt-1.png",
        backend="comfyui",
        prompt_id="prompt-1",
        error=None,
        duration_ms=125,
        attempts=1,
    )

    assert result.status == "success"
    assert result.image_path == "renders/prompt-1.png"
    assert result.prompt_id == "prompt-1"


def test_success_render_result_rejects_missing_image() -> None:
    with pytest.raises(ValidationError, match="successful render requires image_path"):
        RenderResult(
            status="success",
            image_path=None,
            backend="comfyui",
            prompt_id="prompt-1",
            error=None,
            duration_ms=1,
            attempts=1,
        )


def test_failed_render_result_requires_diagnostic_and_no_image() -> None:
    result = RenderResult(
        status="failed",
        image_path=None,
        backend="comfyui",
        prompt_id="prompt-1",
        error="history request failed",
        duration_ms=10,
        attempts=1,
    )

    assert result.status == "failed"
    assert result.prompt_id == "prompt-1"
    assert result.error == "history request failed"


def test_failed_render_result_rejects_hidden_error() -> None:
    with pytest.raises(ValidationError, match="failed render requires error"):
        RenderResult(
            status="failed",
            image_path=None,
            backend="comfyui",
            prompt_id=None,
            error=None,
            duration_ms=10,
            attempts=1,
        )


def test_renderer_health_exposes_availability_version_and_error() -> None:
    available = RendererHealth(
        renderer_available=True,
        backend="comfyui",
        backend_version="0.3.50",
        error=None,
    )
    unavailable = RendererHealth(
        renderer_available=False,
        backend="comfyui",
        backend_version=None,
        error="connection refused",
    )

    assert available.backend_version == "0.3.50"
    assert unavailable.error == "connection refused"

"""Local-machine ComfyUI adapter settings."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import Field, ValidationError, model_validator

from epos.domain.base import DomainModel
from epos.domain.errors import ConfigurationError


class ComfyUIAdapterSettings(DomainModel):
    endpoint: str = Field(min_length=1)
    ws_endpoint: str | None = None
    output_directory: Path
    request_timeout_seconds: float = Field(default=15.0, gt=0.0, le=300.0)
    render_timeout_seconds: float = Field(default=180.0, gt=0.0, le=1800.0)
    poll_interval_seconds: float = Field(default=0.25, gt=0.0, le=30.0)
    retry_delay_seconds: float = Field(default=0.25, ge=0.0, le=30.0)
    max_attempts: int = Field(default=3, ge=1, le=3)

    @model_validator(mode="after")
    def validate_urls(self) -> ComfyUIAdapterSettings:
        endpoint = self.endpoint.strip().rstrip("/")
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("ComfyUI endpoint must use http:// or https://")
        object.__setattr__(self, "endpoint", endpoint)

        if self.ws_endpoint is not None:
            ws_endpoint = self.ws_endpoint.strip()
            if not ws_endpoint.startswith(("ws://", "wss://")):
                raise ValueError("ComfyUI ws_endpoint must use ws:// or wss://")
            object.__setattr__(self, "ws_endpoint", ws_endpoint)
        return self

    @classmethod
    def from_env(
        cls,
        *,
        output_directory: Path,
        environ: Mapping[str, str] | None = None,
    ) -> ComfyUIAdapterSettings:
        values = os.environ if environ is None else environ
        mode = values.get("EPOS_RENDER_MODE")
        if mode is not None and mode.strip().casefold() != "comfyui":
            raise ConfigurationError(
                f"EPOS_RENDER_MODE must be comfyui for ComfyUIAdapter, got {mode!r}"
            )
        endpoint = values.get("EPOS_COMFYUI_ENDPOINT")
        if endpoint is None or not endpoint.strip():
            raise ConfigurationError("EPOS_COMFYUI_ENDPOINT is required for ComfyUI")
        raw: dict[str, object] = {
            "endpoint": endpoint,
            "ws_endpoint": values.get("EPOS_COMFYUI_WS_ENDPOINT"),
            "output_directory": output_directory,
        }
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            raise ConfigurationError(f"invalid ComfyUI adapter configuration: {exc}") from exc

"""Local-machine A1111/Forge adapter settings."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import Field, ValidationError, field_validator, model_validator

from epos.domain.base import DomainModel
from epos.domain.errors import ConfigurationError


class A1111AdapterSettings(DomainModel):
    base_url: str = Field(min_length=1)
    checkpoint: str = Field(min_length=1)
    output_directory: Path
    request_timeout_seconds: float = Field(default=180.0, gt=0.0, le=1800.0)

    @field_validator("checkpoint")
    @classmethod
    def normalize_checkpoint(cls, checkpoint: str) -> str:
        value = checkpoint.strip()
        if not value:
            raise ValueError("A1111 checkpoint must not be empty")
        return value

    @model_validator(mode="after")
    def validate_url(self) -> A1111AdapterSettings:
        base_url = self.base_url.strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("A1111 base_url must use http:// or https://")
        object.__setattr__(self, "base_url", base_url)
        return self

    @classmethod
    def from_env(
        cls,
        *,
        output_directory: Path,
        environ: Mapping[str, str] | None = None,
    ) -> A1111AdapterSettings:
        values = os.environ if environ is None else environ
        mode = values.get("EPOS_RENDER_MODE")
        if mode is not None and mode.strip().casefold() != "a1111":
            raise ConfigurationError(
                f"EPOS_RENDER_MODE must be a1111 for A1111ForgeAdapter, got {mode!r}"
            )
        base_url = values.get("A1111_BASE_URL")
        checkpoint = values.get("A1111_CHECKPOINT")
        missing = tuple(
            name
            for name, value in (
                ("A1111_BASE_URL", base_url),
                ("A1111_CHECKPOINT", checkpoint),
            )
            if value is None or not value.strip()
        )
        if missing:
            raise ConfigurationError(f"missing {', '.join(missing)} for A1111/Forge")

        raw: dict[str, object] = {
            "base_url": base_url,
            "checkpoint": checkpoint,
            "output_directory": output_directory,
        }
        timeout = values.get("A1111_TIMEOUT_SECONDS")
        if timeout is not None and timeout.strip():
            raw["request_timeout_seconds"] = timeout
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            raise ConfigurationError(f"invalid A1111/Forge adapter configuration: {exc}") from exc

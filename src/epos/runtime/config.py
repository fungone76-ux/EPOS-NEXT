"""Local-machine configuration loaded from an uncommitted project ``.env`` file."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values
from pydantic import Field, model_validator

from epos.application.visual.prompt import PromptCompilerProfile
from epos.domain.base import DomainModel
from epos.domain.errors import ConfigurationError

_CANONICAL_IMAGE_SAMPLER = "DPM++ 2M"
_CANONICAL_IMAGE_SCHEDULER = "Karras"
_CANONICAL_IMAGE_STEPS = 24
_CANONICAL_IMAGE_CFG = 7.0


class LocalRuntimeSettings(DomainModel):
    project_root: Path
    data_directory: Path
    worldpacks_directory: Path
    default_worldpack_id: str = Field(min_length=1)
    prompt_profile: PromptCompilerProfile
    environment: dict[str, str]

    @model_validator(mode="after")
    def validate_directories(self) -> LocalRuntimeSettings:
        if not self.project_root.is_dir():
            raise ValueError(f"project directory not found: {self.project_root}")
        if not self.worldpacks_directory.is_dir():
            raise ValueError(f"worldpacks directory not found: {self.worldpacks_directory}")
        return self


def load_local_settings(
    project_root: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> LocalRuntimeSettings:
    """Load ``.env`` first and let the real process environment override it."""
    root = project_root.resolve()
    file_values = {
        key: value
        for key, value in dotenv_values(root / ".env").items()
        if value is not None
    }
    merged = dict(file_values)
    process_values = os.environ if environ is None else environ
    merged.update({key: value for key, value in process_values.items()})

    data_directory = _path_value(root, merged.get("EPOS_DATA_DIRECTORY"), "runtime_data")
    worldpacks_directory = _path_value(root, merged.get("EPOS_WORLDPACKS_DIRECTORY"), "worldpacks")
    profile = PromptCompilerProfile(
        quality_layer=_csv(merged.get("EPOS_IMAGE_QUALITY_LAYER", "masterpiece,best quality")),
        checkpoint=_optional(merged.get("EPOS_IMAGE_CHECKPOINT")),
        width=_integer(merged, "EPOS_IMAGE_WIDTH", 896, minimum=64),
        height=_integer(merged, "EPOS_IMAGE_HEIGHT", 1152, minimum=64),
        sampler=_optional(merged.get("EPOS_IMAGE_SAMPLER")) or _CANONICAL_IMAGE_SAMPLER,
        scheduler=(
            _optional(merged.get("EPOS_IMAGE_SCHEDULER")) or _CANONICAL_IMAGE_SCHEDULER
        ),
        steps=_integer(
            merged,
            "EPOS_IMAGE_STEPS",
            _CANONICAL_IMAGE_STEPS,
            minimum=1,
        ),
        cfg=_float(
            merged,
            "EPOS_IMAGE_CFG",
            _CANONICAL_IMAGE_CFG,
            minimum=0.0,
        ),
    )
    try:
        return LocalRuntimeSettings(
            project_root=root,
            data_directory=data_directory,
            worldpacks_directory=worldpacks_directory,
            default_worldpack_id=merged.get("EPOS_DEFAULT_WORLDPACK", "resort_world").strip(),
            prompt_profile=profile,
            environment=merged,
        )
    except ValueError as exc:
        raise ConfigurationError(f"invalid local EPOS configuration: {exc}") from exc


def _path_value(root: Path, raw: str | None, default: str) -> Path:
    path = Path(raw.strip()) if raw is not None and raw.strip() else Path(default)
    return path if path.is_absolute() else root / path


def _optional(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _csv(raw: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _integer(
    values: Mapping[str, str],
    name: str,
    default: int,
    *,
    minimum: int,
) -> int:
    raw = _optional(values.get(name))
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    return value


def _float(
    values: Mapping[str, str],
    name: str,
    default: float,
    *,
    minimum: float,
) -> float:
    raw = _optional(values.get(name))
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be numeric") from exc
    if value <= minimum:
        raise ConfigurationError(f"{name} must be greater than {minimum:g}")
    return value
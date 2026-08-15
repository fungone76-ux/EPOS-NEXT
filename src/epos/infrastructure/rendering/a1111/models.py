"""Strict A1111/Forge request and profile contracts."""

from __future__ import annotations

from pydantic import Field, JsonValue, ValidationError, field_validator

from epos.domain.base import DomainModel
from epos.domain.errors import ConfigurationError
from epos.domain.world_state import RenderingConfig


class A1111LoraWeightRule(DomainModel):
    alias: str = Field(min_length=1)
    weight: float = Field(ge=-10.0, le=10.0)

    @field_validator("alias")
    @classmethod
    def normalize_alias(cls, alias: str) -> str:
        value = alias.strip()
        if not value:
            raise ValueError("A1111 LoRA alias must not be empty")
        return value


class A1111RenderProfile(DomainModel):
    default_lora_weight: float = Field(default=1.0, ge=-10.0, le=10.0)
    lora_weights: tuple[A1111LoraWeightRule, ...] = ()
    dimension_multiple: int = Field(default=8, ge=1, le=128)
    min_dimension: int = Field(default=64, ge=1, le=4096)
    max_dimension: int = Field(default=4096, ge=64, le=16384)

    @field_validator("lora_weights")
    @classmethod
    def validate_unique_aliases(
        cls,
        rules: tuple[A1111LoraWeightRule, ...],
    ) -> tuple[A1111LoraWeightRule, ...]:
        seen: set[str] = set()
        for rule in rules:
            key = rule.alias.casefold()
            if key in seen:
                raise ValueError(f"duplicate A1111 LoRA weight alias: {rule.alias}")
            seen.add(key)
        return rules

    @classmethod
    def from_rendering_config(cls, config: RenderingConfig) -> A1111RenderProfile:
        raw = config.settings.get("a1111")
        if raw is None:
            raise ConfigurationError("A1111 render profile is missing from Worldpack")
        if not isinstance(raw, dict):
            raise ConfigurationError("invalid A1111 render profile: expected object")
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            raise ConfigurationError(f"invalid A1111 render profile: {exc}") from exc

    def lora_weight_for(self, alias: str) -> float:
        key = alias.casefold()
        for rule in self.lora_weights:
            if rule.alias.casefold() == key:
                return rule.weight
        return self.default_lora_weight


class A1111RenderRequest(DomainModel):
    request_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    negative_prompt: str
    seed: int = Field(ge=0, le=2**64 - 1)
    width: int = Field(ge=64)
    height: int = Field(ge=64)
    sampler_name: str | None = None
    scheduler: str | None = None
    steps: int | None = Field(default=None, ge=1)
    cfg_scale: float | None = Field(default=None, gt=0.0)
    batch_size: int = Field(default=1, ge=1, le=1)
    n_iter: int = Field(default=1, ge=1, le=1)
    override_settings: dict[str, JsonValue]
    override_settings_restore_afterwards: bool = True

    def api_payload(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "batch_size": self.batch_size,
            "n_iter": self.n_iter,
            "override_settings": dict(self.override_settings),
            "override_settings_restore_afterwards": self.override_settings_restore_afterwards,
        }
        if self.sampler_name is not None:
            payload["sampler_name"] = self.sampler_name
        if self.scheduler is not None:
            payload["scheduler"] = self.scheduler
        if self.steps is not None:
            payload["steps"] = self.steps
        if self.cfg_scale is not None:
            payload["cfg_scale"] = self.cfg_scale
        return payload

"""Backend-neutral render contracts returned to application/orchestration layers."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from epos.domain.base import DomainModel


class RendererHealth(DomainModel):
    renderer_available: bool
    backend: str = Field(min_length=1)
    backend_version: str | None = None
    error: str | None = None

    @model_validator(mode="after")
    def validate_health(self) -> RendererHealth:
        if self.renderer_available and self.error is not None:
            raise ValueError("available renderer must not expose an error")
        if not self.renderer_available and not (self.error or "").strip():
            raise ValueError("unavailable renderer requires an error")
        return self


class RenderResult(DomainModel):
    status: Literal["success", "failed"]
    image_path: str | None
    backend: str = Field(min_length=1)
    prompt_id: str | None
    error: str | None
    duration_ms: int = Field(ge=0)
    attempts: int = Field(ge=1, le=3)

    @model_validator(mode="after")
    def validate_result(self) -> RenderResult:
        if self.status == "success":
            if not (self.image_path or "").strip():
                raise ValueError("successful render requires image_path")
            if not (self.prompt_id or "").strip():
                raise ValueError("successful render requires prompt_id")
            if self.error is not None:
                raise ValueError("successful render must not expose an error")
        else:
            if self.image_path is not None:
                raise ValueError("failed render must not expose image_path")
            if not (self.error or "").strip():
                raise ValueError("failed render requires error")
        return self

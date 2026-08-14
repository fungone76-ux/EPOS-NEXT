"""Python validation for raw Visual Semantic Tables."""

from __future__ import annotations

from epos.application.visual.vst.context import VisualDirectorContext
from epos.application.visual.vst.models import RawVST
from epos.domain.errors import EposValidationError


class VSTValidationError(EposValidationError):
    def __init__(self, message: str, *, code: str = "visual.vst.validation_failed") -> None:
        super().__init__(message, code=code)


class RawVSTValidator:
    """Validate contract identity only; Module 12 owns world canonicalization."""

    def validate(self, raw: RawVST, context: VisualDirectorContext) -> RawVST:
        if raw.scene_id != context.scene_id:
            raise VSTValidationError(
                f"VST scene_id {raw.scene_id} does not match context {context.scene_id}"
            )
        return raw

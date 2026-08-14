"""Coordinate Visual Director context, LLM invocation, and raw VST validation."""

from __future__ import annotations

from epos.application.ports import LLMPort
from epos.application.visual.models import ObservableSceneState
from epos.application.visual.vst.context import (
    VisualDirectorContext,
    VisualDirectorContextBuilder,
)
from epos.application.visual.vst.models import RawVST
from epos.application.visual.vst.validation import RawVSTValidator


class VisualDirectorService:
    def __init__(
        self,
        *,
        port: LLMPort[VisualDirectorContext, RawVST],
        context_builder: VisualDirectorContextBuilder | None = None,
        validator: RawVSTValidator | None = None,
    ) -> None:
        self._port = port
        self._context_builder = context_builder or VisualDirectorContextBuilder()
        self._validator = validator or RawVSTValidator()

    async def generate(self, scene: ObservableSceneState) -> RawVST:
        context = self._context_builder.build(scene)
        raw = await self._port.invoke(context)
        return self._validator.validate(raw, context)

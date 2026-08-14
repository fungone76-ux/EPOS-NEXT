"""Renderer port definitions."""

from __future__ import annotations

from typing import Protocol, TypeVar

from epos.application.visual.rendering.models import RendererHealth, RenderResult

RequestT = TypeVar("RequestT", contravariant=True)


class RendererPort(Protocol[RequestT]):
    async def health_check(self) -> RendererHealth: ...

    async def render(self, request: RequestT) -> RenderResult: ...

"""Backend-neutral visual renderer boundary."""

from epos.application.visual.rendering.errors import (
    RendererConnectionError,
    RendererExecutionError,
    RendererProtocolError,
)
from epos.application.visual.rendering.models import RendererHealth, RenderResult
from epos.application.visual.rendering.ports import RendererPort

__all__ = [
    "RenderResult",
    "RendererConnectionError",
    "RendererExecutionError",
    "RendererHealth",
    "RendererPort",
    "RendererProtocolError",
]

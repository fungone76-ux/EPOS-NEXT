"""Classified renderer failures for the application boundary."""

from epos.domain.errors import ExternalServiceError


class RendererConnectionError(ExternalServiceError):
    """The renderer endpoint could not be reached reliably."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="renderer.connection")


class RendererExecutionError(ExternalServiceError):
    """The renderer accepted work but execution failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="renderer.execution")


class RendererProtocolError(ExternalServiceError):
    """The renderer returned an invalid or incompatible protocol payload."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="renderer.protocol")

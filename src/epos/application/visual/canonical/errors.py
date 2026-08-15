"""Errors raised by Module 12 visual canonicalization."""

from epos.domain.errors import VisualContractError


class VisualCanonicalizationError(VisualContractError):
    """Raised when RAW visual intent contradicts canonical visual truth."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "visual.canonical.invalid",
    ) -> None:
        super().__init__(message, code=code)


class SemanticLibraryResolutionError(VisualCanonicalizationError):
    """Raised when semantic intent cannot map to exactly one library entry."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="visual.canonical.library.invalid")

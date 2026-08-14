"""Errors owned by the Module 16 visual bridge."""

from epos.domain.errors import PersistenceError


class VisualDiagnosticsPersistenceError(PersistenceError):
    """Raised when a visual pipeline snapshot cannot be persisted safely."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="visual.diagnostics.persistence_failed")

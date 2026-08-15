"""Public Module 19 turn-result boundary."""

from epos.application.results.mapper import TurnResultMapper
from epos.application.results.models import (
    TurnCheckResult,
    TurnDiagnostics,
    TurnDialogueLine,
    TurnGameResult,
    TurnIssue,
    TurnResult,
    TurnVisualLora,
    TurnVisualResult,
)

__all__ = [
    "TurnCheckResult",
    "TurnDiagnostics",
    "TurnDialogueLine",
    "TurnGameResult",
    "TurnIssue",
    "TurnResult",
    "TurnResultMapper",
    "TurnVisualLora",
    "TurnVisualResult",
]

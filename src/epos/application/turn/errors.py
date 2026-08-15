"""Explicit Module 18 turn orchestration failures."""

from epos.domain.errors import EposValidationError


class TurnOrchestrationError(EposValidationError):
    def __init__(self, message: str, *, code: str = "turn.orchestration_invalid") -> None:
        super().__init__(message, code=code)


class CheckDecisionRequiredError(TurnOrchestrationError):
    def __init__(self, message: str = "player decision required before rolling check") -> None:
        super().__init__(message, code="turn.check_decision_required")


class PendingDiceCheckpointError(TurnOrchestrationError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="turn.pending_dice_checkpoint")


class TurnCommitMismatchError(TurnOrchestrationError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="turn.commit_mismatch")

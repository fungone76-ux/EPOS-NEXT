"""Deterministic recovery policy; failures always become explicit decisions."""

from __future__ import annotations

from dataclasses import dataclass

from epos.application.recovery.errors import (
    CheckResolutionError,
    ConfigurationError,
    LLMContractError,
    LLMError,
    MemoryError,
    PersistenceError,
    PromptCompilationError,
    RendererConnectionError,
    RendererExecutionError,
    StateValidationError,
    VisualContractError,
    WorkflowValidationError,
    WorldpackValidationError,
)
from epos.application.recovery.models import RecoveryAction, RecoveryDecision
from epos.domain.errors import ContractError, EposError, EposValidationError, ExternalServiceError


@dataclass(frozen=True, slots=True)
class _Rule:
    error: type[Exception]
    action: RecoveryAction
    retryable: bool
    http_status: int


_RULES = (
    _Rule(WorldpackValidationError, RecoveryAction.FIX_WORLDPACK, False, 422),
    _Rule(LLMContractError, RecoveryAction.RETRY_TURN, True, 502),
    _Rule(LLMError, RecoveryAction.RETRY_TURN, True, 502),
    _Rule(StateValidationError, RecoveryAction.RESUME_SESSION, True, 409),
    _Rule(CheckResolutionError, RecoveryAction.RETRY_TURN, False, 422),
    _Rule(MemoryError, RecoveryAction.RETRY_MEMORY, True, 503),
    _Rule(VisualContractError, RecoveryAction.RETRY_TURN, True, 422),
    _Rule(PromptCompilationError, RecoveryAction.RETRY_TURN, True, 422),
    _Rule(WorkflowValidationError, RecoveryAction.FIX_WORKFLOW, False, 422),
    _Rule(RendererConnectionError, RecoveryAction.RETRY_IMAGE, True, 503),
    _Rule(RendererExecutionError, RecoveryAction.RETRY_IMAGE, True, 502),
    _Rule(PersistenceError, RecoveryAction.RETRY_PERSISTENCE, True, 503),
    _Rule(ConfigurationError, RecoveryAction.RECONFIGURE, False, 503),
    _Rule(ContractError, RecoveryAction.RETRY_TURN, False, 422),
    _Rule(EposValidationError, RecoveryAction.RETRY_TURN, False, 422),
    _Rule(ExternalServiceError, RecoveryAction.RETRY_TURN, True, 502),
    _Rule(EposError, RecoveryAction.REPORT_BUG, False, 400),
)


class ErrorRecoveryPolicy:
    """Classify an exception without retrying or mutating authoritative state."""

    def decide(
        self,
        error: Exception,
        *,
        phase: str,
        committed: bool = False,
    ) -> RecoveryDecision:
        normalized_phase = phase.strip() or "unknown"
        for rule in _RULES:
            if isinstance(error, rule.error):
                code = error.code if isinstance(error, EposError) else "epos.error"
                return RecoveryDecision(
                    error_type=type(error).__name__,
                    code=code,
                    message=str(error),
                    phase=normalized_phase,
                    action=rule.action,
                    retryable=rule.retryable,
                    http_status=rule.http_status,
                    committed_state_preserved=committed,
                    replay_turn=(rule.action is RecoveryAction.RETRY_TURN and not committed),
                )

        return RecoveryDecision(
            error_type=type(error).__name__,
            code=f"unexpected.{normalized_phase}",
            message=f"{type(error).__name__}: {error}",
            phase=normalized_phase,
            action=RecoveryAction.REPORT_BUG,
            retryable=False,
            http_status=500,
            committed_state_preserved=committed,
            replay_turn=False,
        )

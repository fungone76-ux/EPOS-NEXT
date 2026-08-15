"""Typed recovery decisions shared by presentation and orchestration boundaries."""

from enum import StrEnum

from pydantic import Field

from epos.domain.base import DomainModel


class RecoveryAction(StrEnum):
    RECONFIGURE = "reconfigure"
    FIX_WORLDPACK = "fix_worldpack"
    RETRY_TURN = "retry_turn"
    RESUME_SESSION = "resume_session"
    RETRY_MEMORY = "retry_memory"
    FIX_WORKFLOW = "fix_workflow"
    RETRY_IMAGE = "retry_image"
    RETRY_PERSISTENCE = "retry_persistence"
    REPORT_BUG = "report_bug"


class RecoveryDecision(DomainModel):
    error_type: str = Field(min_length=1)
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    action: RecoveryAction
    retryable: bool
    http_status: int = Field(ge=400, le=599)
    committed_state_preserved: bool = False
    replay_turn: bool = False

"""Module 09/18 state-authority errors."""

from epos.domain.errors import EposValidationError


class StateMutationError(EposValidationError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="state.mutation_invalid")


class MutationAuthorityError(StateMutationError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = "state.mutation_authority"


class StaleAuthoritativeStateError(StateMutationError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = "state.stale_authoritative_state"


class CheckpointStateMismatchError(EposValidationError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="state.checkpoint_mismatch")

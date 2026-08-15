"""Stable EPOS exception hierarchy.

Detailed subsystem errors will be added by the module that owns the relevant
behaviour. Module 00 defines only broad architectural categories.
"""


class EposError(Exception):
    """Base exception for expected EPOS failures."""

    def __init__(self, message: str, *, code: str = "epos.error") -> None:
        super().__init__(message)
        self.code = code


class ContractError(EposError):
    """A typed boundary contract was invalid."""

    def __init__(self, message: str, *, code: str = "contract.invalid") -> None:
        super().__init__(message, code=code)


class ConfigurationError(EposError):
    """Static application or adapter configuration is invalid."""

    def __init__(self, message: str, *, code: str = "configuration.invalid") -> None:
        super().__init__(message, code=code)


class EposValidationError(EposError):
    """A domain/application invariant failed validation."""

    def __init__(self, message: str, *, code: str = "validation.failed") -> None:
        super().__init__(message, code=code)


class StateValidationError(EposValidationError):
    """Authoritative state is invalid, stale, or unsafe to commit."""

    def __init__(self, message: str, *, code: str = "state.validation_failed") -> None:
        super().__init__(message, code=code)


class MemoryError(EposError):
    """Memory capture, recall, consolidation, or storage failed."""

    def __init__(self, message: str, *, code: str = "memory.failed") -> None:
        super().__init__(message, code=code)


class VisualContractError(ContractError):
    """A visual semantic contract is invalid or contradicts authority."""

    def __init__(self, message: str, *, code: str = "visual.contract.invalid") -> None:
        super().__init__(message, code=code)


class PromptCompilationError(EposValidationError):
    """Python could not deterministically compile a validated visual contract."""

    def __init__(self, message: str, *, code: str = "visual.prompt.compilation_failed") -> None:
        super().__init__(message, code=code)


class ExternalServiceError(EposError):
    """An external dependency failed in a classified way."""

    def __init__(self, message: str, *, code: str = "external_service.failed") -> None:
        super().__init__(message, code=code)


class PersistenceError(EposError):
    """Persistence could not complete safely."""

    def __init__(self, message: str, *, code: str = "persistence.failed") -> None:
        super().__init__(message, code=code)

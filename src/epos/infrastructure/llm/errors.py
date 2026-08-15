"""Classified errors for the EPOS NEXT LLM boundary."""

from epos.domain.errors import ConfigurationError, ContractError, ExternalServiceError


class LLMError(ExternalServiceError):
    def __init__(self, message: str, *, code: str = "llm.failed") -> None:
        super().__init__(message, code=code)


class LLMTransportError(LLMError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="llm.transport.failed")


class LLMProviderResponseError(LLMError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="llm.provider_response.invalid")


class LLMContractError(ContractError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="llm.contract.invalid")


class LLMUnavailableError(ConfigurationError):
    def __init__(self, message: str = "LLM unavailable") -> None:
        super().__init__(message, code="llm.unavailable")

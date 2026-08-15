"""Classified errors for the EPOS NEXT LLM boundary."""

from epos.domain.errors import ConfigurationError, ContractError, ExternalServiceError


class LLMError(ExternalServiceError):
    def __init__(self, message: str, *, code: str = "llm.failed") -> None:
        super().__init__(message, code=code)


class LLMTransportError(LLMError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="llm.transport.failed")


class LLMProviderResponseError(LLMError):
    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        code = "llm.rate_limited" if http_status == 429 else "llm.provider_response.invalid"
        super().__init__(message, code=code)
        self.http_status = http_status


class LLMContractError(ContractError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="llm.contract.invalid")


class LLMUnavailableError(ConfigurationError):
    def __init__(self, message: str = "LLM unavailable") -> None:
        super().__init__(message, code="llm.unavailable")

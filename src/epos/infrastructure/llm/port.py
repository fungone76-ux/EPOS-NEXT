"""Typed structured-output LLMPort with the only retry/fallback policy layer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Generic, TypeVar, cast

from pydantic import BaseModel, ValidationError

from epos.domain.json_types import ensure_json_object
from epos.infrastructure.llm.backends import StructuredLLMBackend
from epos.infrastructure.llm.errors import (
    LLMContractError,
    LLMError,
    LLMProviderResponseError,
    LLMUnavailableError,
)
from epos.infrastructure.llm.models import (
    LLMRetryPolicy,
    LLMTask,
    StructuredLLMRepairInput,
    StructuredLLMRequest,
)
from epos.infrastructure.llm.runtime import LLMRuntime
from epos.infrastructure.llm.tasks import TASK_PROFILES

RequestT = TypeVar("RequestT", bound=BaseModel)
ResponseT = TypeVar("ResponseT", bound=BaseModel)

_STRICT_OUTPUT_INSTRUCTION = (
    " Return exactly one object that satisfies the supplied strict JSON schema. "
    "Copy identifiers exactly from the supplied input; never translate, reformat, or invent "
    "an identifier. A semantic token is one lowercase value without spaces, using only "
    "letters, digits, underscore, hyphen, dot, or colon. Respect every enum, bound, length, "
    "uniqueness rule, field description, and cross-field relationship. Use null or an empty "
    "array for optional information that is unsupported by the input."
)

_REPAIR_INSTRUCTION = (
    " This is a contract-repair attempt. The previous object passed provider-side JSON Schema "
    "generation but failed local Pydantic validation. Read the supplied validation errors and "
    "return a corrected object only. Preserve supported facts from the original input, fix the "
    "listed violations, and do not copy the repair envelope into the response."
)


def _schema_name(model: type[BaseModel]) -> str:
    filtered = "".join(
        character
        for character in model.__name__
        if character.isalnum() or character in "_-"
    )
    name = filtered[:64]
    return name or "epos_response"


def _validation_errors_json(error: ValidationError) -> str:
    return error.json(include_url=False, include_context=False, include_input=False)


def _repair_request(
    original: StructuredLLMRequest,
    *,
    invalid_output_json: str,
    error: ValidationError,
) -> StructuredLLMRequest:
    repair_input = StructuredLLMRepairInput(
        original_input_json=original.input_json,
        invalid_output_json=invalid_output_json,
        validation_errors_json=_validation_errors_json(error),
    )
    return original.model_copy(
        update={
            "system_instruction": original.system_instruction + _REPAIR_INSTRUCTION,
            "input_json": repair_input.model_dump_json(),
        }
    )


class StructuredLLMPort(Generic[RequestT, ResponseT]):
    """Adapt Pydantic request/response pairs to configured structured LLM backends."""

    def __init__(
        self,
        *,
        task: LLMTask,
        response_model: type[ResponseT],
        runtime: LLMRuntime | None = None,
        backends: Sequence[StructuredLLMBackend] | None = None,
        retry_policy: LLMRetryPolicy | None = None,
    ) -> None:
        if runtime is not None and backends is not None:
            raise ValueError("provide runtime or backends, not both")
        selected = runtime.backends if runtime is not None else tuple(backends or ())
        if not selected:
            raise LLMUnavailableError()
        self._backends = tuple(selected)
        self._task = task
        self._response_model = response_model
        self._retry_policy = retry_policy or LLMRetryPolicy()

    async def invoke(self, request: RequestT) -> ResponseT:
        profile = TASK_PROFILES[self._task]
        raw_schema = self._response_model.model_json_schema()
        json_schema = ensure_json_object(cast(Mapping[str, object], raw_schema))
        provider_request = StructuredLLMRequest(
            task=self._task,
            system_instruction=profile.system_instruction + _STRICT_OUTPUT_INSTRUCTION,
            input_json=request.model_dump_json(),
            schema_name=_schema_name(self._response_model),
            json_schema=json_schema,
        )

        last_error: LLMError | LLMContractError | None = None
        provider_failures: dict[str, str] = {}
        for backend in self._backends:
            provider_label = f"{backend.provider.value}/{backend.model}"
            attempt_request = provider_request
            for _attempt in range(self._retry_policy.max_attempts_per_provider):
                try:
                    completion = await backend.complete(attempt_request)
                    return self._response_model.model_validate_json(completion.text)
                except ValidationError as exc:
                    last_error = LLMContractError(
                        f"{backend.provider.value} returned output outside the Pydantic contract: "
                        f"{_validation_errors_json(exc)}"
                    )
                    last_error.__cause__ = exc
                    provider_failures[provider_label] = str(last_error)
                    attempt_request = _repair_request(
                        provider_request,
                        invalid_output_json=completion.text,
                        error=exc,
                    )
                except LLMProviderResponseError as exc:
                    last_error = exc
                    provider_failures[provider_label] = str(exc)
                    if exc.http_status is not None and (
                        exc.http_status == 429
                        or (400 <= exc.http_status < 500 and exc.http_status != 408)
                    ):
                        break
                except (LLMError, LLMContractError) as exc:
                    last_error = exc
                    provider_failures[provider_label] = str(exc)

        detail = "; ".join(
            f"{provider}: {message}" for provider, message in provider_failures.items()
        )
        message = "all configured LLM providers failed"
        if detail:
            message = f"{message} ({detail})"
        failure = LLMError(
            message,
            code="llm.all_providers_failed",
        )
        if last_error is None:
            raise failure
        raise failure from last_error

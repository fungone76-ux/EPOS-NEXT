"""Typed structured-output LLMPort with the only retry/fallback policy layer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Generic, TypeVar, cast

from pydantic import BaseModel, ValidationError

from epos.domain.json_types import ensure_json_object
from epos.infrastructure.llm.backends import StructuredLLMBackend
from epos.infrastructure.llm.errors import LLMContractError, LLMError, LLMUnavailableError
from epos.infrastructure.llm.models import LLMRetryPolicy, LLMTask, StructuredLLMRequest
from epos.infrastructure.llm.runtime import LLMRuntime
from epos.infrastructure.llm.tasks import TASK_PROFILES

RequestT = TypeVar("RequestT", bound=BaseModel)
ResponseT = TypeVar("ResponseT", bound=BaseModel)


def _schema_name(model: type[BaseModel]) -> str:
    filtered = "".join(character for character in model.__name__ if character.isalnum() or character in "_-")
    name = filtered[:64]
    return name or "epos_response"


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
        schema = ensure_json_object(cast(Mapping[str, object], raw_schema))
        provider_request = StructuredLLMRequest(
            task=self._task,
            system_instruction=profile.system_instruction,
            input_json=request.model_dump_json(),
            schema_name=_schema_name(self._response_model),
            schema=schema,
        )

        last_error: LLMError | LLMContractError | None = None
        for backend in self._backends:
            for _attempt in range(self._retry_policy.max_attempts_per_provider):
                try:
                    completion = await backend.complete(provider_request)
                    return self._response_model.model_validate_json(completion.text)
                except ValidationError as exc:
                    last_error = LLMContractError(
                        f"{backend.provider.value} returned output outside the Pydantic contract"
                    )
                    last_error.__cause__ = exc
                except (LLMError, LLMContractError) as exc:
                    last_error = exc

        failure = LLMError(
            "all configured LLM providers failed",
            code="llm.all_providers_failed",
        )
        if last_error is None:
            raise failure
        raise failure from last_error

"""Typed cache decorator for structured LLM ports."""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from epos.infrastructure.cache.ports import LLMResponseCachePort

RequestT = TypeVar("RequestT", bound=BaseModel)
ResponseT = TypeVar("ResponseT", bound=BaseModel)
RequestContraT = TypeVar("RequestContraT", bound=BaseModel, contravariant=True)
ResponseCovariantT = TypeVar("ResponseCovariantT", bound=BaseModel, covariant=True)


class StructuredInvocationPort(Protocol[RequestContraT, ResponseCovariantT]):
    async def invoke(self, request: RequestContraT) -> ResponseCovariantT: ...


class CachedStructuredLLMPort(Generic[RequestT, ResponseT]):
    def __init__(
        self,
        *,
        source: StructuredInvocationPort[RequestT, ResponseT],
        cache: LLMResponseCachePort,
        response_model: type[ResponseT],
        namespace: str,
    ) -> None:
        self._source = source
        self._cache = cache
        self._response_model = response_model
        self._namespace = namespace

    async def invoke(self, request: RequestT) -> ResponseT:
        request_json = request.model_dump_json()
        cached = await self._cache.get(
            namespace=self._namespace,
            request_json=request_json,
        )
        if cached is not None:
            try:
                return self._response_model.model_validate_json(cached.response_json)
            except ValidationError:
                pass

        response = await self._source.invoke(request)
        await self._cache.put(
            namespace=self._namespace,
            request_json=request_json,
            response_json=response.model_dump_json(),
        )
        return response

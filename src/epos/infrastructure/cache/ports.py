"""Embedding and cache ports used by cache-aware LLM adapters."""

from __future__ import annotations

from typing import Protocol

from epos.infrastructure.cache.models import CachedLLMResponse


class TextEmbeddingPort(Protocol):
    async def embed(self, text: str) -> tuple[float, ...]: ...


class LLMResponseCachePort(Protocol):
    async def get(self, *, namespace: str, request_json: str) -> CachedLLMResponse | None: ...

    async def put(
        self,
        *,
        namespace: str,
        request_json: str,
        response_json: str,
    ) -> None: ...

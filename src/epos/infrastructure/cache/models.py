"""Cache records and lookup results."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from epos.domain.base import DomainModel


class CachedLLMResponse(DomainModel):
    response_json: str
    kind: Literal["exact", "semantic"]
    similarity: float = Field(ge=-1.0, le=1.0)


class ImageCacheRecord(DomainModel):
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_path: str = Field(min_length=1)
    backend: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)

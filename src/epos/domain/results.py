"""Structured success/failure contracts for application boundaries."""

from __future__ import annotations

from typing import Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Serializable diagnostic returned at recoverable boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    retryable: bool = False
    context: dict[str, JsonValue] = Field(default_factory=dict)


class Success(BaseModel, Generic[T]):
    """Successful operation result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: Literal[True] = True
    value: T


class Failure(BaseModel):
    """Classified operation failure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: Literal[False] = False
    error: ErrorDetail

Result: TypeAlias = Success[T] | Failure

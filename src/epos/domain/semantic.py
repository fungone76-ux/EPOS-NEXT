"""Reusable semantic-token contract exposed to Pydantic and provider JSON schemas."""

from __future__ import annotations

from typing import Annotated, TypeAlias

from pydantic import BeforeValidator, StringConstraints

SEMANTIC_TOKEN_PATTERN = r"^[a-z0-9][a-z0-9_.:-]*$"


def _normalize_semantic_token_input(value: object) -> object:
    if isinstance(value, str):
        return value.strip().casefold()
    return value


SemanticToken: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=SEMANTIC_TOKEN_PATTERN),
    BeforeValidator(_normalize_semantic_token_input),
]

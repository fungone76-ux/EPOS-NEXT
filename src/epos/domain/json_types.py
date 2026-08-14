"""JSON-safe recursive value types and boundary validation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TypeAlias, cast

from epos.domain.errors import ContractError

JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
JSONObject: TypeAlias = dict[str, JSONValue]


def _ensure_json_value(value: object, *, path: str) -> JSONValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractError(
                f"Non-finite float at {path}",
                code="invalid_json_value",
            )
        return value
    if isinstance(value, list):
        items = cast(list[object], value)
        return [
            _ensure_json_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(items)
        ]
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        result: JSONObject = {}
        for key, item in mapping.items():
            if not isinstance(key, str):
                raise ContractError(
                    f"Non-string JSON object key at {path}",
                    code="invalid_json_value",
                )
            result[key] = _ensure_json_value(item, path=f"{path}.{key}")
        return result
    raise ContractError(
        f"Unsupported JSON value {type(value).__name__} at {path}",
        code="invalid_json_value",
    )


def ensure_json_object(value: Mapping[str, object]) -> JSONObject:
    """Validate unknown boundary data and return a JSON-safe deep copy."""

    result: JSONObject = {}
    for key, item in value.items():
        result[key] = _ensure_json_value(item, path=f"$.{key}")
    return result

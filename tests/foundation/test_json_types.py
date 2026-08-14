from epos.domain.errors import ContractError
from epos.domain.json_types import ensure_json_object


def test_json_object_accepts_recursive_json_values() -> None:
    payload = {"a": [1, 2, {"nested": True}], "b": None, "c": "ok"}
    assert ensure_json_object(payload) == payload


def test_json_object_rejects_non_json_values() -> None:
    try:
        ensure_json_object({"bad": object()})  # type: ignore[dict-item]
    except ContractError as exc:
        assert exc.code == "invalid_json_value"
    else:
        raise AssertionError("non JSON-safe values must be rejected")

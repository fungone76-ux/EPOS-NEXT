import pytest
from pydantic import ValidationError

from epos.domain.errors import ContractError, EposError
from epos.domain.results import ErrorDetail, Failure, Success


def test_error_hierarchy_carries_stable_code() -> None:
    err = ContractError("bad contract", code="contract.invalid")
    assert isinstance(err, EposError)
    assert err.code == "contract.invalid"
    assert str(err) == "bad contract"


def test_result_contracts_forbid_extra_fields() -> None:
    success = Success[int](value=7)
    failure = Failure(error=ErrorDetail(code="x", message="boom", retryable=False))
    assert success.ok is True
    assert failure.ok is False

    with pytest.raises(ValidationError):
        ErrorDetail(code="x", message="boom", surprise=True)  # type: ignore[call-arg]

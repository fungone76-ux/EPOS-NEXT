import pytest
from pydantic import ValidationError

from epos.application.psychology import PsychologyProfile


def test_psychology_profile_rejects_negative_sensitivity() -> None:
    with pytest.raises(ValidationError):
        PsychologyProfile(anger_sensitivity=-0.01)


def test_psychology_profile_rejects_negative_decay() -> None:
    with pytest.raises(ValidationError):
        PsychologyProfile(anger_decay_per_time_unit=-0.01)


def test_psychology_profile_forbids_unknown_configuration() -> None:
    with pytest.raises(ValidationError):
        PsychologyProfile(unknown_tuning=1.0)

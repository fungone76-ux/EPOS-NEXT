from __future__ import annotations

import pytest

from epos.application.actions.checks import (
    CheckResolutionError,
    CheckResolver,
    D6OutcomePolicy,
)
from epos.application.actions.models import CheckOutcome, CheckProposal
from epos.domain.ids import SkillId


class _SequenceRandom:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)
        self.bounds: list[tuple[int, int]] = []

    def randint(self, lower: int, upper: int) -> int:
        self.bounds.append((lower, upper))
        return self.values.pop(0)


def _proposal(difficulty: int = 4) -> CheckProposal:
    return CheckProposal(skill_id=SkillId("negoziazione"), difficulty=difficulty)


def test_rating_is_exact_d6_pool_size_and_python_owns_rolls() -> None:
    rng = _SequenceRandom([6, 4, 2, 1])

    result = CheckResolver(D6OutcomePolicy()).resolve(_proposal(), rating=4, rng=rng)

    assert result.pool_size == 4
    assert result.dice == (6, 4, 2, 1)
    assert result.success_count == 2
    assert result.outcome is CheckOutcome.FULL_SUCCESS
    assert rng.bounds == [(1, 6)] * 4


@pytest.mark.parametrize(
    ("dice", "expected"),
    [
        ([6, 2, 2, 2], CheckOutcome.PARTIAL_SUCCESS),
        ([3, 2, 2, 1], CheckOutcome.FAILURE),
        ([1, 1, 1], CheckOutcome.CRITICAL_FAILURE),
    ],
)
def test_baseline_outcome_policy_is_deterministic(
    dice: list[int], expected: CheckOutcome
) -> None:
    result = CheckResolver(D6OutcomePolicy()).resolve(
        _proposal(), rating=len(dice), rng=_SequenceRandom(dice)
    )

    assert result.outcome is expected


def test_difficulty_is_strictly_between_one_and_six() -> None:
    with pytest.raises(ValueError):
        CheckProposal(skill_id=SkillId("negoziazione"), difficulty=0)
    with pytest.raises(ValueError):
        CheckProposal(skill_id=SkillId("negoziazione"), difficulty=7)


def test_missing_or_zero_rating_cannot_silently_roll() -> None:
    with pytest.raises(CheckResolutionError, match="rating"):
        CheckResolver(D6OutcomePolicy()).resolve(
            _proposal(), rating=0, rng=_SequenceRandom([])
        )


def test_invalid_random_source_value_is_rejected() -> None:
    with pytest.raises(CheckResolutionError, match="outside d6 range"):
        CheckResolver(D6OutcomePolicy()).resolve(
            _proposal(), rating=1, rng=_SequenceRandom([9])
        )

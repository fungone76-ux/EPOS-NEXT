"""Pure Python d6 check resolution. No LLM and no global random state."""

from typing import Protocol

from epos.application.actions.models import CheckOutcome, CheckProposal, ResolvedCheck
from epos.domain.errors import EposValidationError
from epos.domain.rng import RandomSource


class CheckResolutionError(EposValidationError):
    def __init__(self, message: str, *, code: str = "check.resolution.failed") -> None:
        super().__init__(message, code=code)


class OutcomePolicy(Protocol):
    """Replaceable Python policy for mapping a canonical d6 pool to an outcome."""

    def outcome(
        self,
        *,
        dice: tuple[int, ...],
        difficulty: int,
        success_count: int,
    ) -> CheckOutcome: ...


class D6OutcomePolicy:
    """Explicit provisional baseline until Product Owner fixes a canonical mapping."""

    def outcome(
        self,
        *,
        dice: tuple[int, ...],
        difficulty: int,
        success_count: int,
    ) -> CheckOutcome:
        del difficulty
        if success_count >= 2:
            return CheckOutcome.FULL_SUCCESS
        if success_count == 1:
            return CheckOutcome.PARTIAL_SUCCESS
        if dice and all(die == 1 for die in dice):
            return CheckOutcome.CRITICAL_FAILURE
        return CheckOutcome.FAILURE


class CheckResolver:
    """Roll an injected RNG and produce a canonical immutable check result."""

    def __init__(self, policy: OutcomePolicy) -> None:
        self._policy = policy

    def resolve(
        self,
        proposal: CheckProposal,
        *,
        rating: int,
        rng: RandomSource,
    ) -> ResolvedCheck:
        if rating < 1:
            raise CheckResolutionError("skill rating must be at least 1")

        rolled: list[int] = []
        for _ in range(rating):
            die = rng.randint(1, 6)
            if not 1 <= die <= 6:
                raise CheckResolutionError(f"random source produced value outside d6 range: {die}")
            rolled.append(die)

        dice = tuple(rolled)
        success_count = sum(die >= proposal.difficulty for die in dice)
        outcome = self._policy.outcome(
            dice=dice,
            difficulty=proposal.difficulty,
            success_count=success_count,
        )
        return ResolvedCheck(
            skill_id=proposal.skill_id,
            difficulty=proposal.difficulty,
            rating=rating,
            pool_size=rating,
            dice=dice,
            success_count=success_count,
            outcome=outcome,
        )

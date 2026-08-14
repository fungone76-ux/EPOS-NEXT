from datetime import UTC, datetime

from epos.domain.clock import Clock
from epos.domain.rng import RandomSource


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 14, 10, 0, tzinfo=UTC)


class FixedRandom:
    def randint(self, lower: int, upper: int) -> int:
        assert lower <= upper
        return lower


def test_clock_and_rng_are_structural_protocols() -> None:
    clock: Clock = FixedClock()
    rng: RandomSource = FixedRandom()
    assert clock.now().tzinfo is UTC
    assert rng.randint(1, 6) == 1

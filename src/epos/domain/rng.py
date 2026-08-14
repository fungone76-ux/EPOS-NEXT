"""Random-source abstraction. Game systems never call random globally."""

from typing import Protocol


class RandomSource(Protocol):
    """Injected randomness source used by Python-authoritative systems."""

    def randint(self, lower: int, upper: int) -> int:
        """Return an integer in the inclusive range [lower, upper]."""
        ...

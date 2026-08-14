"""Clock abstraction for deterministic domain/application tests."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Source of canonical current time for services that need it."""

    def now(self) -> datetime:
        """Return the current timezone-aware instant."""
        ...

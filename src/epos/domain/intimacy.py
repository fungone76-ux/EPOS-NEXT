"""Persistent adult intimacy state for NPCs only."""

from pydantic import Field

from epos.domain.base import DomainModel
from epos.domain.ids import TurnNumber


class IntimacyState(DomainModel):
    sexual_attraction: float = Field(default=0.0, ge=0.0, le=10.0)
    desire: float = Field(default=0.0, ge=0.0, le=10.0)
    arousal: float = Field(default=0.0, ge=0.0, le=10.0)
    comfort: float = Field(default=0.0, ge=0.0, le=10.0)
    tension: float = Field(default=0.0, ge=0.0, le=10.0)
    completed_sexual_encounters: int = Field(default=0, ge=0)
    last_intimate_turn: TurnNumber | None = None

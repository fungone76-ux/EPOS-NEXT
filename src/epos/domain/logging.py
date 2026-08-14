"""Structured log context shared by all EPOS layers."""

from pydantic import BaseModel, ConfigDict

from epos.domain.ids import EntityId, SessionId, TurnNumber


class LogContext(BaseModel):
    """Stable correlation fields for structured events."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    phase: str
    session_id: SessionId | None = None
    turn_number: TurnNumber | None = None
    provider: str | None = None
    npc_id: EntityId | None = None
    renderer: str | None = None

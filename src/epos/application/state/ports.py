"""Checkpoint persistence port for exact post-roll crash recovery."""

from __future__ import annotations

from typing import Protocol

from epos.application.state.models import DiceCheckpoint
from epos.domain.ids import SessionId


class DiceCheckpointStorePort(Protocol):
    async def save(self, checkpoint: DiceCheckpoint) -> None: ...

    async def load(self, session_id: SessionId) -> DiceCheckpoint | None: ...

    async def delete(self, session_id: SessionId) -> None: ...

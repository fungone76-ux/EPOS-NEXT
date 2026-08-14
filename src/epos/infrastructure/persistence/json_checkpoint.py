"""Atomic JSON persistence adapter for exact post-roll checkpoints."""

from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import quote

from pydantic import ValidationError

from epos.application.state.models import DiceCheckpoint
from epos.domain.errors import PersistenceError
from epos.domain.ids import SessionId
from epos.infrastructure.persistence.atomic_files import atomic_write_bytes


class JsonFileCheckpointStore:
    def __init__(self, *, root: Path) -> None:
        self._root = root

    def checkpoint_path(self, session_id: SessionId) -> Path:
        token = quote(str(session_id), safe="")
        return self._root / f"{token}.dice-checkpoint.json"

    async def save(self, checkpoint: DiceCheckpoint) -> None:
        await asyncio.to_thread(self._save_sync, checkpoint)

    async def load(self, session_id: SessionId) -> DiceCheckpoint | None:
        return await asyncio.to_thread(self._load_sync, session_id)

    async def delete(self, session_id: SessionId) -> None:
        await asyncio.to_thread(self._delete_sync, session_id)

    def _save_sync(self, checkpoint: DiceCheckpoint) -> None:
        target = self.checkpoint_path(checkpoint.session_id)
        payload = checkpoint.model_dump_json(indent=2).encode("utf-8")
        atomic_write_bytes(target, payload)

    def _load_sync(self, session_id: SessionId) -> DiceCheckpoint | None:
        target = self.checkpoint_path(session_id)
        if not target.exists():
            return None
        try:
            checkpoint = DiceCheckpoint.model_validate_json(
                target.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as exc:
            raise PersistenceError(f"could not load dice checkpoint: {exc}") from exc
        if checkpoint.session_id != session_id:
            raise PersistenceError("checkpoint session_id does not match persistence key")
        return checkpoint

    def _delete_sync(self, session_id: SessionId) -> None:
        target = self.checkpoint_path(session_id)
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            raise PersistenceError(f"could not delete dice checkpoint: {exc}") from exc

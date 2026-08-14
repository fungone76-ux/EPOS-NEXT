"""JSON WorldState persistence with temp-write, fsync, replace, and LKG backup."""

from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import quote

from pydantic import ValidationError

from epos.infrastructure.persistence.atomic_files import atomic_write_bytes
from epos.domain.errors import PersistenceError
from epos.domain.ids import SessionId
from epos.domain.world_state import WorldState


class JsonFileStateStore:
    def __init__(self, *, root: Path) -> None:
        self._root = root

    def state_path(self, session_id: SessionId) -> Path:
        return self._root / f"{_session_token(session_id)}.state.json"

    def backup_path(self, session_id: SessionId) -> Path:
        return self._root / f"{_session_token(session_id)}.state.json.bak"

    def temp_path(self, session_id: SessionId) -> Path:
        path = self.state_path(session_id)
        return path.with_name(f"{path.name}.tmp")

    async def save(self, session_id: SessionId, state: WorldState) -> None:
        if state.session_id != session_id:
            raise PersistenceError("state session_id does not match persistence key")
        await asyncio.to_thread(self._save_sync, session_id, state)

    async def load(self, session_id: SessionId) -> WorldState:
        return await asyncio.to_thread(self._load_sync, session_id)

    def _save_sync(self, session_id: SessionId, state: WorldState) -> None:
        target = self.state_path(session_id)
        backup = self.backup_path(session_id)
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            try:
                previous = target.read_bytes()
            except OSError as exc:
                raise PersistenceError(
                    f"could not read current state before backup: {exc}"
                ) from exc
            atomic_write_bytes(backup, previous)

        payload = state.model_dump_json(indent=2).encode("utf-8")
        atomic_write_bytes(target, payload)

    def _load_sync(self, session_id: SessionId) -> WorldState:
        target = self.state_path(session_id)
        backup = self.backup_path(session_id)
        failures: list[str] = []

        for candidate in (target, backup):
            if not candidate.exists():
                continue
            try:
                state = WorldState.model_validate_json(candidate.read_text(encoding="utf-8"))
            except (OSError, ValidationError) as exc:
                failures.append(f"{candidate.name}: {exc}")
                continue
            if state.session_id != session_id:
                failures.append(
                    f"{candidate.name}: session mismatch {state.session_id}"
                )
                continue
            return state

        detail = "; ".join(failures) if failures else "no state or backup file exists"
        raise PersistenceError(f"could not load authoritative state: {detail}")


def _session_token(session_id: SessionId) -> str:
    return quote(str(session_id), safe="")

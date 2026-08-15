"""Atomic JSON persistence for one pending image per session."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from epos.application.visual.recovery import PendingRender
from epos.domain.ids import SessionId, TurnNumber
from epos.infrastructure.persistence.atomic_files import atomic_write_bytes

_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]+")


class JsonPendingRenderStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    async def save(self, pending: PendingRender) -> str:
        target = self._path(pending.session_id)
        payload = (
            json.dumps(
                pending.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        await asyncio.to_thread(atomic_write_bytes, target, payload)
        return str(target)

    async def load(self, session_id: SessionId) -> PendingRender | None:
        target = self._path(session_id)
        if not target.exists():
            return None
        payload = await asyncio.to_thread(target.read_text, encoding="utf-8")
        return PendingRender.model_validate_json(payload)

    async def delete(self, session_id: SessionId, turn_number: TurnNumber) -> None:
        current = await self.load(session_id)
        if current is None or current.turn_number != turn_number:
            return
        await asyncio.to_thread(self._path(session_id).unlink, missing_ok=True)

    def _path(self, session_id: SessionId) -> Path:
        safe = _SAFE_ID.sub("_", str(session_id)).strip("_")[:160] or "session"
        return self._root / f"{safe}.pending-render.json"

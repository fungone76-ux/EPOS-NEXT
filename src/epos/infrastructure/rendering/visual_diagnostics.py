"""Atomic persistence for prepared and rendered visual-pipeline diagnostics."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from epos.application.visual.bridge import (
    VisualDiagnosticsPersistenceError,
    VisualPipelineDiagnostics,
)
from epos.domain.errors import PersistenceError
from epos.infrastructure.persistence.atomic_files import atomic_write_bytes

_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]+")


class AtomicVisualDiagnosticsStore:
    def __init__(self, output_directory: Path) -> None:
        self._output_directory = output_directory

    async def save(self, snapshot: VisualPipelineDiagnostics) -> str:
        safe_scene_id = _SAFE_ID.sub("_", str(snapshot.scene_id)).strip("_")[:160]
        if not safe_scene_id:
            safe_scene_id = "visual_scene"
        target = self._output_directory / f"{safe_scene_id}.visual.json"
        payload = (
            json.dumps(
                snapshot.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        try:
            await asyncio.to_thread(atomic_write_bytes, target, payload)
        except PersistenceError as exc:
            raise VisualDiagnosticsPersistenceError(
                f"visual diagnostics persistence failed for {snapshot.scene_id}: {exc}"
            ) from exc
        return str(target)

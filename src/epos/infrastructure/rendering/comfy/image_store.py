"""Atomic local persistence for rendered image bytes."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Protocol

from epos.infrastructure.persistence.atomic_files import atomic_write_bytes

_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]+")
_SAFE_SUFFIX = re.compile(r"^\.[A-Za-z0-9]{1,10}$")


class RenderImageStoreProtocol(Protocol):
    async def save(
        self,
        *,
        prompt_id: str,
        remote_filename: str,
        payload: bytes,
    ) -> str: ...


class AtomicRenderImageStore:
    def __init__(self, output_directory: Path) -> None:
        self._output_directory = output_directory

    async def save(
        self,
        *,
        prompt_id: str,
        remote_filename: str,
        payload: bytes,
    ) -> str:
        safe_id = _SAFE_ID.sub("_", prompt_id).strip("_")[:128]
        if not safe_id:
            safe_id = "render"

        suffix = Path(remote_filename).suffix.lower()
        if not _SAFE_SUFFIX.fullmatch(suffix):
            suffix = ".png"

        target = self._output_directory / f"{safe_id}{suffix}"
        await asyncio.to_thread(atomic_write_bytes, target, payload)
        return str(target)

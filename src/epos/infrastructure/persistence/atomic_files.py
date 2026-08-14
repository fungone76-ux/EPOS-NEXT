"""Blocking atomic-file primitives used only behind asyncio.to_thread adapters."""

from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path

from epos.domain.errors import PersistenceError


def atomic_write_bytes(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f"{target.name}.tmp")
    try:
        with temp.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
        _fsync_directory(target.parent)
    except OSError as exc:
        with suppress(OSError):
            temp.unlink(missing_ok=True)
        raise PersistenceError(
            f"atomic write failed for {target.name}: {exc}"
        ) from exc


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

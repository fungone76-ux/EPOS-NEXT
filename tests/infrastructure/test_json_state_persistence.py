from __future__ import annotations

import os
from pathlib import Path

import pytest

from epos.domain.errors import PersistenceError
from epos.domain.ids import EntityId, LocationId, SessionId, WorldpackId
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, WorldState
from epos.infrastructure.persistence.json_state import JsonFileStateStore


def _world(*, day: int) -> WorldState:
    return WorldState(
        session_id=SessionId("session-1"),
        worldpack_id=WorldpackId("test-world"),
        turn_number=2,
        day=day,
        world_phase="morning",
        player=PlayerState(
            entity_id=EntityId("player"),
            name="Player",
            location_id=LocationId("lobby"),
        ),
        locations={
            LocationId("lobby"): LocationState(
                location_id=LocationId("lobby"),
                name="Lobby",
            )
        },
    )


@pytest.mark.asyncio
async def test_json_state_store_writes_atomically_and_keeps_backup(tmp_path: Path) -> None:
    store = JsonFileStateStore(root=tmp_path)
    first = _world(day=1)
    second = _world(day=2)

    await store.save(first.session_id, first)
    await store.save(second.session_id, second)

    assert await store.load(first.session_id) == second
    assert store.backup_path(first.session_id).exists()
    assert not store.temp_path(first.session_id).exists()

    store.state_path(first.session_id).write_text("{broken", encoding="utf-8")

    assert await store.load(first.session_id) == first


@pytest.mark.asyncio
async def test_failed_atomic_replace_keeps_previous_authoritative_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = JsonFileStateStore(root=tmp_path)
    first = _world(day=1)
    second = _world(day=2)
    await store.save(first.session_id, first)

    def fail_replace(src: str | bytes | os.PathLike[str] | os.PathLike[bytes], dst: str | bytes | os.PathLike[str] | os.PathLike[bytes]) -> None:
        del src, dst
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(PersistenceError, match="atomic"):
        await store.save(second.session_id, second)

    assert await store.load(first.session_id) == first
    assert not store.temp_path(first.session_id).exists()

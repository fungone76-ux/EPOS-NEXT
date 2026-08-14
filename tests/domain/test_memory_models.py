import pytest
from pydantic import ValidationError

from epos.domain.ids import EntityId, MemoryId, TurnNumber
from epos.domain.memory import MemoryCapsuleState, MemoryEntryState, MemoryKind


def test_memory_entry_is_strict_bounded_and_typed() -> None:
    memory = MemoryEntryState(
        memory_id=MemoryId("m1"),
        turn=TurnNumber(10),
        summary="Victoria kept the player's promise in mind.",
        participants=(EntityId("player"), EntityId("victoria")),
        salience=7.5,
        kind=MemoryKind.EPISODIC,
    )

    assert memory.salience == 7.5

    with pytest.raises(ValidationError):
        MemoryEntryState(
            memory_id=MemoryId("m2"),
            turn=TurnNumber(11),
            summary="invalid",
            salience=10.01,
        )


def test_capsule_keeps_python_owned_provenance() -> None:
    capsule = MemoryCapsuleState(
        memory_id=MemoryId("capsule-1"),
        turn=TurnNumber(40),
        summary="A week of increasingly cooperative conversations.",
        source_memory_ids=(MemoryId("m1"), MemoryId("m2")),
        themes=("cooperation", "trust"),
        unresolved_threads=("pool incident",),
    )

    assert capsule.kind is MemoryKind.CAPSULE
    assert capsule.source_memory_ids == (MemoryId("m1"), MemoryId("m2"))

from epos.application.memory import LongTermMemoryRecord, MemoryRecallQuery
from epos.domain.ids import EntityId, MemoryId, TurnNumber
from epos.domain.memory import MemoryEntryState
from epos.infrastructure.memory.simple import SimpleMemoryAdapter


async def test_simple_adapter_isolates_npc_archives() -> None:
    store = SimpleMemoryAdapter()
    victoria = EntityId("victoria")
    luna = EntityId("luna")

    await store.add(
        LongTermMemoryRecord(
            npc_id=victoria,
            memory=MemoryEntryState(
                memory_id=MemoryId("v1"),
                turn=TurnNumber(1),
                summary="Victoria discussed the statues with the player.",
            ),
        )
    )
    await store.add(
        LongTermMemoryRecord(
            npc_id=luna,
            memory=MemoryEntryState(
                memory_id=MemoryId("l1"),
                turn=TurnNumber(1),
                summary="Luna hid a letter in her room.",
            ),
        )
    )

    hits = await store.recall(
        MemoryRecallQuery(
            npc_id=victoria,
            player_input="statues",
            scene_context="lobby",
            current_goals=(),
            current_turn=TurnNumber(5),
        ),
        limit=5,
    )

    assert [hit.memory.memory_id for hit in hits] == [MemoryId("v1")]

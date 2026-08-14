import threading

from epos.application.memory import LongTermMemoryRecord, MemoryHit, MemoryRecallQuery
from epos.domain.ids import EntityId, MemoryId, TurnNumber
from epos.domain.memory import MemoryEntryState
from epos.infrastructure.memory.chroma import ChromaMemoryAdapter, SyncChromaMemoryCollection


class FakeSyncCollection(SyncChromaMemoryCollection):
    def __init__(self) -> None:
        self.thread_ids: list[int] = []
        self.records: list[LongTermMemoryRecord] = []

    def add(self, record: LongTermMemoryRecord) -> None:
        self.thread_ids.append(threading.get_ident())
        self.records.append(record)

    def recall(self, query: MemoryRecallQuery, *, limit: int) -> list[MemoryHit]:
        self.thread_ids.append(threading.get_ident())
        return [
            MemoryHit(memory=record.memory, semantic_score=1.0)
            for record in self.records[:limit]
        ]


async def test_chroma_sync_boundary_runs_outside_event_loop_thread() -> None:
    loop_thread = threading.get_ident()
    collection = FakeSyncCollection()
    adapter = ChromaMemoryAdapter(collection)
    npc_id = EntityId("victoria")
    record = LongTermMemoryRecord(
        npc_id=npc_id,
        memory=MemoryEntryState(
            memory_id=MemoryId("m1"),
            turn=TurnNumber(1),
            summary="Victoria remembers the statues.",
        ),
    )

    await adapter.add(record)
    hits = await adapter.recall(
        MemoryRecallQuery(
            npc_id=npc_id,
            player_input="statues",
            scene_context="lobby",
            current_goals=(),
            current_turn=TurnNumber(2),
        ),
        limit=3,
    )

    assert hits[0].memory.memory_id == MemoryId("m1")
    assert collection.thread_ids
    assert all(thread_id != loop_thread for thread_id in collection.thread_ids)

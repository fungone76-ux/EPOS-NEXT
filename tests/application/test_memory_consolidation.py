from epos.application.memory import (
    ConsolidationPolicy,
    MemoryConsolidationService,
    MemorySummarizerPort,
    MemorySummaryDraft,
    MemorySummaryRequest,
)
from epos.domain.ids import EntityId, MemoryId, TurnNumber
from epos.domain.memory import MemoryEntryState, MemoryKind

NPC_ID = EntityId("victoria")


class FakeSummarizer(MemorySummarizerPort):
    def __init__(self) -> None:
        self.requests: list[MemorySummaryRequest] = []

    async def summarize(self, request: MemorySummaryRequest) -> MemorySummaryDraft:
        self.requests.append(request)
        return MemorySummaryDraft(
            summary="A cluster of routine conversations gradually improved cooperation.",
            themes=("cooperation", "routine"),
            unresolved_threads=("pool misunderstanding",),
            emotional_summary="Mildly warmer and less guarded.",
        )


def make_memory(index: int, *, protected: bool = False, tag: str | None = None) -> MemoryEntryState:
    tags = () if tag is None else (tag,)
    return MemoryEntryState(
        memory_id=MemoryId(f"m{index}"),
        turn=TurnNumber(index),
        summary=f"routine resort conversation {index}",
        participants=(NPC_ID,),
        salience=3.0,
        protected=protected,
        tags=tags,
    )


async def test_consolidation_runs_only_after_python_policy_triggers() -> None:
    summarizer = FakeSummarizer()
    service = MemoryConsolidationService(
        summarizer=summarizer,
        policy=ConsolidationPolicy(trigger_count=6, batch_size=4, min_age_turns=5),
    )

    too_small = tuple(make_memory(index) for index in range(5))
    no_result = await service.consolidate(
        npc_id=NPC_ID,
        memories=too_small,
        current_turn=TurnNumber(30),
        capsule_id=MemoryId("capsule-none"),
    )

    assert no_result is None
    assert summarizer.requests == []


async def test_python_selects_sources_and_llm_only_writes_structured_summary() -> None:
    summarizer = FakeSummarizer()
    service = MemoryConsolidationService(
        summarizer=summarizer,
        policy=ConsolidationPolicy(trigger_count=6, batch_size=4, min_age_turns=5),
    )
    memories = tuple(make_memory(index) for index in range(8))

    result = await service.consolidate(
        npc_id=NPC_ID,
        memories=memories,
        current_turn=TurnNumber(30),
        capsule_id=MemoryId("capsule-1"),
    )

    assert result is not None
    assert result.original_memories == memories
    assert len(summarizer.requests) == 1
    assert result.capsule.source_memory_ids == tuple(
        memory.memory_id for memory in summarizer.requests[0].memories
    )
    assert result.capsule.kind is MemoryKind.CAPSULE


async def test_protected_and_critical_memories_are_never_selected_for_compression() -> None:
    summarizer = FakeSummarizer()
    service = MemoryConsolidationService(
        summarizer=summarizer,
        policy=ConsolidationPolicy(trigger_count=4, batch_size=4, min_age_turns=5),
    )
    memories = (
        make_memory(1, protected=True),
        make_memory(2, tag="promise"),
        make_memory(3, tag="betrayal"),
        make_memory(4, tag="confession"),
        make_memory(5, tag="secret_discovery"),
        make_memory(6, tag="relationship_milestone"),
        make_memory(7),
        make_memory(8),
        make_memory(9),
        make_memory(10),
    )

    result = await service.consolidate(
        npc_id=NPC_ID,
        memories=memories,
        current_turn=TurnNumber(30),
        capsule_id=MemoryId("capsule-2"),
    )

    assert result is not None
    selected_ids = set(result.capsule.source_memory_ids)
    assert selected_ids == {MemoryId("m7"), MemoryId("m8"), MemoryId("m9"), MemoryId("m10")}

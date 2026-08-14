from epos.application.memory import (
    LongTermMemoryRecord,
    MemoryCapturePolicy,
    MemoryRecallQuery,
    MemoryRecallService,
    MemoryService,
)
from epos.domain.ids import EntityId, LocationId, MemoryId, TurnNumber
from epos.domain.memory import EmotionalMemoryState, MemoryEntryState, MemoryKind
from epos.domain.npc import NPCIdentity, NPCState
from epos.infrastructure.memory.simple import SimpleMemoryAdapter

NPC_ID = EntityId("victoria")
PLAYER_ID = EntityId("player")


def npc() -> NPCState:
    return NPCState(
        identity=NPCIdentity(entity_id=NPC_ID, name="Victoria", role="director"),
        location_id=LocationId("lobby"),
    )


def memory(index: int, *, kind: MemoryKind = MemoryKind.EPISODIC) -> MemoryEntryState:
    return MemoryEntryState(
        memory_id=MemoryId(f"m{index}"),
        turn=TurnNumber(index),
        summary=f"event {index}",
        participants=(PLAYER_ID, NPC_ID),
        salience=5.0,
        kind=kind,
    )


def test_short_term_memory_is_bounded_and_only_records_perceived_events() -> None:
    service = MemoryService(MemoryCapturePolicy(short_term_limit=16))
    state = npc()

    for index in range(20):
        state = service.remember(state, memory(index), perceived=True)

    assert len(state.short_term_memory) == 16
    assert state.short_term_memory[0].memory_id == MemoryId("m4")

    unchanged = service.remember(state, memory(21), perceived=False)
    assert unchanged == state


def test_core_and_emotional_memories_are_kept_in_their_own_layers() -> None:
    service = MemoryService.default()
    state = npc()
    core = memory(1, kind=MemoryKind.CORE)
    emotional = EmotionalMemoryState(
        memory_id=MemoryId("em1"),
        turn=TurnNumber(2),
        summary="Victoria felt humiliated in front of the staff.",
        participants=(PLAYER_ID, NPC_ID),
        salience=9.0,
        emotion="shame",
        intensity=8.0,
    )

    state = service.remember(state, core, perceived=True)
    state = service.remember(state, emotional, perceived=True)

    assert state.core_memories == (core,)
    assert state.emotional_memory == (emotional,)


async def test_recall_uses_player_input_scene_and_goals_and_returns_only_few_hits() -> None:
    store = SimpleMemoryAdapter()
    for item in (
        MemoryEntryState(
            memory_id=MemoryId("statues"),
            turn=TurnNumber(1),
            summary="The player asked Victoria about the marble statues near the lobby.",
            participants=(PLAYER_ID, NPC_ID),
            salience=5.0,
        ),
        MemoryEntryState(
            memory_id=MemoryId("pool"),
            turn=TurnNumber(2),
            summary="Victoria argued with the player beside the swimming pool.",
            participants=(PLAYER_ID, NPC_ID),
            salience=7.0,
        ),
        MemoryEntryState(
            memory_id=MemoryId("kitchen"),
            turn=TurnNumber(3),
            summary="Victoria discussed kitchen inventory with the chef.",
            participants=(NPC_ID,),
            salience=2.0,
        ),
    ):
        await store.add(LongTermMemoryRecord(npc_id=NPC_ID, memory=item))

    service = MemoryRecallService(store)
    query = MemoryRecallQuery(
        npc_id=NPC_ID,
        player_input="Victoria, what were you saying about those statues?",
        scene_context="We are standing in the resort lobby beside the marble statues.",
        current_goals=("understand what the player wants",),
        current_turn=TurnNumber(20),
    )

    result = await service.recall(query, limit=2)

    assert len(result.memories) == 2
    assert result.memories[0].memory.memory_id == MemoryId("statues")
    assert "statues" in result.query_text

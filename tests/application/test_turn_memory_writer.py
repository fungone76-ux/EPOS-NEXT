from __future__ import annotations

import pytest

from epos.application.actions.models import ValidatedAction
from epos.application.conversation.models import (
    ConversationFocus,
    NarrationMode,
    NarrationResult,
    WorldNarrationDraft,
)
from epos.application.memory import LongTermMemoryRecord, MemoryService
from epos.application.state import ReplaceNPCMemoryLayersMutation
from epos.application.turn import TurnMemoryContext, TurnMemoryCoordinator, TurnOrchestrationError
from epos.application.visual.models import SceneObservationInput
from epos.application.visual.observable_scene import ObservableSceneBuilder
from epos.domain.ids import EntityId, LocationId, MemoryId, SessionId, WorldpackId
from epos.domain.memory import MemoryEntryState
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, WorldState


def _state() -> WorldState:
    return WorldState(
        session_id=SessionId("session-1"),
        worldpack_id=WorldpackId("test-world"),
        turn_number=2,
        day=1,
        world_phase="morning",
        player=PlayerState(
            entity_id=EntityId("player"),
            name="Player",
            location_id=LocationId("lobby"),
        ),
        npcs={
            EntityId("victoria"): NPCState(
                identity=NPCIdentity(
                    entity_id=EntityId("victoria"),
                    name="Victoria",
                    role="director",
                ),
                location_id=LocationId("lobby"),
            ),
            EntityId("stella"): NPCState(
                identity=NPCIdentity(
                    entity_id=EntityId("stella"),
                    name="Stella",
                    role="guest",
                ),
                location_id=LocationId("garden"),
            ),
        },
        locations={
            LocationId("lobby"): LocationState(
                location_id=LocationId("lobby"), name="Lobby"
            ),
            LocationId("garden"): LocationState(
                location_id=LocationId("garden"), name="Garden"
            ),
        },
    )


def _context() -> TurnMemoryContext:
    state = _state()
    action = ValidatedAction(intent="greet", target_ids=(EntityId("victoria"),))
    scene = ObservableSceneBuilder().build(
        state=state,
        observation=SceneObservationInput(action=action),
    )
    narration = NarrationResult(
        focus=ConversationFocus(
            speaker_id=EntityId("player"),
            target_npc_id=EntityId("victoria"),
            topic="greeting",
            mode=NarrationMode.ACTION,
        ),
        units=(
            WorldNarrationDraft(
                text="Victoria ricambia il saluto.",
                subject_ids=(EntityId("victoria"),),
            ),
        ),
        text="Victoria ricambia il saluto.",
    )
    return TurnMemoryContext(
        state=state,
        player_input="Buongiorno Victoria.",
        action=action,
        scene=scene,
        narration=narration,
    )


def _record(npc_id: str, *, memory_id: str = "memory-1", turn: int = 2) -> LongTermMemoryRecord:
    return LongTermMemoryRecord(
        npc_id=EntityId(npc_id),
        memory=MemoryEntryState(
            memory_id=MemoryId(memory_id),
            turn=turn,
            summary="Il giocatore ha salutato Victoria nella lobby.",
            participants=(EntityId("player"), EntityId("victoria")),
            salience=2.0,
        ),
    )


class FixedDerivation:
    def __init__(self, records: tuple[LongTermMemoryRecord, ...]) -> None:
        self.records = records
        self.context: TurnMemoryContext | None = None
        self.calls = 0

    async def derive(self, context: TurnMemoryContext) -> tuple[LongTermMemoryRecord, ...]:
        self.calls += 1
        self.context = context.model_copy(deep=True)
        return tuple(record.model_copy(deep=True) for record in self.records)


class RecordingMemoryStore:
    def __init__(self) -> None:
        self.added: list[LongTermMemoryRecord] = []

    async def add(self, record: LongTermMemoryRecord) -> None:
        self.added.append(record.model_copy(deep=True))

    async def recall(self, query, *, limit: int):
        return ()


@pytest.mark.asyncio
async def test_turn_memory_derives_once_then_archives_same_record() -> None:
    context = _context()
    record = _record("victoria")
    derivation = FixedDerivation((record,))
    store = RecordingMemoryStore()
    memory = TurnMemoryCoordinator(
        derivation=derivation,
        capture=MemoryService.default(),
        store=store,
    )

    plan = await memory.prepare(context)

    assert derivation.calls == 1
    assert derivation.context == context
    assert plan.records == (record,)
    assert len(plan.mutation_batches) == 1
    mutation = plan.mutation_batches[0].mutations[0]
    assert isinstance(mutation, ReplaceNPCMemoryLayersMutation)
    assert mutation.npc_id == EntityId("victoria")
    assert mutation.short_term_memory == (record.memory,)
    assert store.added == []

    await memory.store(plan)

    assert derivation.calls == 1
    assert store.added == [record]


@pytest.mark.asyncio
async def test_turn_memory_coordinator_rejects_offscene_npc_before_plan_or_store_write() -> None:
    store = RecordingMemoryStore()
    memory = TurnMemoryCoordinator(
        derivation=FixedDerivation(
            (_record("victoria"), _record("stella", memory_id="memory-2"))
        ),
        capture=MemoryService.default(),
        store=store,
    )

    with pytest.raises(TurnOrchestrationError, match="off-scene NPC stella"):
        await memory.prepare(_context())

    assert store.added == []


@pytest.mark.asyncio
async def test_turn_memory_coordinator_rejects_memory_from_wrong_turn() -> None:
    store = RecordingMemoryStore()
    memory = TurnMemoryCoordinator(
        derivation=FixedDerivation((_record("victoria", turn=1),)),
        capture=MemoryService.default(),
        store=store,
    )

    with pytest.raises(TurnOrchestrationError, match="memory turn"):
        await memory.prepare(_context())

    assert store.added == []

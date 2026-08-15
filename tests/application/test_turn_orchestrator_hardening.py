from __future__ import annotations

import pytest

from epos.application.actions.models import CheckProposal, ResolvedCheck, ValidatedAction
from epos.application.conversation.models import (
    ConversationFocus,
    NarrationMode,
    NarrationResult,
    WorldNarrationDraft,
)
from epos.application.memory import LongTermMemoryRecord, MemoryService
from epos.application.state import AuthoritativeStateManager, DiceCheckpoint, DiceCheckpointService
from epos.application.turn import (
    DefaultReactionMutationPlanner,
    DefaultTurnActionResolver,
    DefaultTurnSceneBuilder,
    TurnCommand,
    TurnMemoryCoordinator,
    TurnOrchestrator,
    TurnPsychologyPlan,
)
from epos.application.visual.bridge import VisualPipelineResult
from epos.domain.ids import EntityId, LocationId, MemoryId, SessionId, WorldpackId
from epos.domain.memory import MemoryEntryState
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, WorldState


def _world() -> WorldState:
    return WorldState(
        session_id=SessionId("session-hardening"),
        worldpack_id=WorldpackId("test-world"),
        turn_number=1,
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
            )
        },
        locations={
            LocationId("lobby"): LocationState(
                location_id=LocationId("lobby"),
                name="Lobby",
            )
        },
    )


class StateStore:
    def __init__(self, state: WorldState) -> None:
        self.state = state.model_copy(deep=True)
        self.saved: list[WorldState] = []

    async def load(self, session_id: SessionId) -> WorldState:
        return self.state.model_copy(deep=True)

    async def save(self, session_id: SessionId, state: WorldState) -> None:
        self.state = state.model_copy(deep=True)
        self.saved.append(state.model_copy(deep=True))


class CheckpointStore:
    def __init__(self) -> None:
        self.value: DiceCheckpoint | None = None

    async def save(self, checkpoint: DiceCheckpoint) -> None:
        self.value = checkpoint.model_copy(deep=True)

    async def load(self, session_id: SessionId) -> DiceCheckpoint | None:
        return self.value.model_copy(deep=True) if self.value is not None else None

    async def delete(self, session_id: SessionId) -> None:
        self.value = None


class Interpreter:
    async def interpret(self, context) -> ValidatedAction:
        return ValidatedAction(
            intent="greet",
            target_ids=(EntityId("victoria"),),
        )


class UnusedCheckResolver:
    def resolve(self, proposal: CheckProposal, *, rating: int) -> ResolvedCheck:
        raise AssertionError("unchecked action must not roll dice")


class EmptyPsychology:
    def plan(self, **kwargs) -> TurnPsychologyPlan:
        return TurnPsychologyPlan()


class SilentCognition:
    async def react(self, **kwargs):
        return None


class Narration:
    async def generate(self, **kwargs) -> NarrationResult:
        return NarrationResult(
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


class SuccessfulVisual:
    async def render(self, scene) -> VisualPipelineResult:
        return VisualPipelineResult.model_construct()


class UnexpectedFailingVisual:
    async def render(self, scene) -> VisualPipelineResult:
        raise RuntimeError("driver vanished")


class OneMemoryDerivation:
    def __init__(self) -> None:
        self.calls = 0

    async def derive(self, context) -> tuple[LongTermMemoryRecord, ...]:
        self.calls += 1
        return (
            LongTermMemoryRecord(
                npc_id=EntityId("victoria"),
                memory=MemoryEntryState(
                    memory_id=MemoryId("turn-2-greeting"),
                    turn=context.scene.time.turn_number,
                    summary="Il giocatore ha salutato Victoria nella lobby.",
                    participants=(EntityId("player"), EntityId("victoria")),
                    salience=2.0,
                ),
            ),
        )


class EmptyMemoryDerivation:
    async def derive(self, context) -> tuple[LongTermMemoryRecord, ...]:
        return ()


class MemoryStore:
    def __init__(self) -> None:
        self.added: list[LongTermMemoryRecord] = []

    async def add(self, record: LongTermMemoryRecord) -> None:
        self.added.append(record.model_copy(deep=True))

    async def recall(self, query, *, limit: int):
        return ()


def _orchestrator(*, visual, derivation, state_store: StateStore, memory_store: MemoryStore):
    manager = AuthoritativeStateManager(initial_state=_world(), state_store=state_store)
    memory = TurnMemoryCoordinator(
        derivation=derivation,
        capture=MemoryService.default(),
        store=memory_store,
    )
    return TurnOrchestrator(
        state=manager,
        checkpoint=DiceCheckpointService(store=CheckpointStore()),
        interpreter=Interpreter(),
        check_resolver=UnusedCheckResolver(),
        action_resolver=DefaultTurnActionResolver(),
        psychology=EmptyPsychology(),
        cognition=SilentCognition(),
        reaction_mutations=DefaultReactionMutationPlanner(),
        scene_builder=DefaultTurnSceneBuilder(),
        narration=Narration(),
        visual=visual,
        memory=memory,
    )


@pytest.mark.asyncio
async def test_concrete_memory_is_part_of_single_authoritative_turn_commit() -> None:
    state_store = StateStore(_world())
    memory_store = MemoryStore()
    derivation = OneMemoryDerivation()
    orchestrator = _orchestrator(
        visual=SuccessfulVisual(),
        derivation=derivation,
        state_store=state_store,
        memory_store=memory_store,
    )

    result = await orchestrator.run(TurnCommand(player_input="Buongiorno Victoria."))

    assert len(state_store.saved) == 1
    assert derivation.calls == 1
    expected = MemoryId("turn-2-greeting")
    active = result.committed_state.npcs[EntityId("victoria")].short_term_memory
    assert tuple(memory.memory_id for memory in active) == (expected,)
    assert tuple(record.memory.memory_id for record in memory_store.added) == (expected,)
    assert result.memory_stored is True


@pytest.mark.asyncio
async def test_unexpected_postcommit_visual_error_becomes_issue_not_turn_failure() -> None:
    state_store = StateStore(_world())
    memory_store = MemoryStore()
    orchestrator = _orchestrator(
        visual=UnexpectedFailingVisual(),
        derivation=EmptyMemoryDerivation(),
        state_store=state_store,
        memory_store=memory_store,
    )

    result = await orchestrator.run(TurnCommand(player_input="Buongiorno Victoria."))

    assert len(state_store.saved) == 1
    assert int(result.committed_state.turn_number) == 2
    assert result.memory_stored is True
    assert result.visual is None
    assert len(result.post_commit_issues) == 1
    issue = result.post_commit_issues[0]
    assert issue.phase == "visual"
    assert issue.code == "turn.post_commit.visual_unexpected"
    assert "RuntimeError" in issue.message

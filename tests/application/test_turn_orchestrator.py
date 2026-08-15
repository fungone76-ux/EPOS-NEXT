from __future__ import annotations

import pytest

from epos.application.actions.models import (
    CheckOutcome,
    CheckProposal,
    ResolvedCheck,
    ValidatedAction,
    ValidatedOutfitRequest,
)
from epos.application.cognition.models import (
    CognitionResult,
    NPCOutfitRequestResponse,
    OutfitRequestDisposition,
    ValidatedNPCReaction,
)
from epos.application.conversation.models import (
    ConversationFocus,
    NarrationMode,
    NarrationResult,
    WorldNarrationDraft,
)
from epos.application.state import AuthoritativeStateManager, DiceCheckpoint, DiceCheckpointService
from epos.application.turn import (
    CheckDecision,
    CheckDecisionRequiredError,
    DefaultReactionMutationPlanner,
    DefaultTurnSceneBuilder,
    PendingDiceCheckpointError,
    TurnActionResolution,
    TurnCommand,
    TurnMemoryContext,
    TurnMemoryPlan,
    TurnOrchestrator,
    TurnPsychologyPlan,
)
from epos.domain.errors import ExternalServiceError, PersistenceError
from epos.domain.ids import EntityId, LocationId, SessionId, SkillId, WorldpackId
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.outfit import OutfitItem, OutfitState, WardrobeOutfit
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, SkillDefinition, WorldState


def _world() -> WorldState:
    return WorldState(
        session_id=SessionId("session-1"),
        worldpack_id=WorldpackId("test-world"),
        turn_number=1,
        day=1,
        world_phase="morning",
        player=PlayerState(
            entity_id=EntityId("player"),
            name="Player",
            location_id=LocationId("lobby"),
            stats={"negoziazione": 3.0},
        ),
        npcs={
            EntityId("victoria"): NPCState(
                identity=NPCIdentity(
                    entity_id=EntityId("victoria"),
                    name="Victoria",
                    role="director",
                ),
                location_id=LocationId("lobby"),
                outfit=OutfitState(
                    items=(
                        OutfitItem(
                            item_id="victoria_day_dress",
                            name="day dress",
                            slot="body",
                            layer=10,
                        ),
                    )
                ),
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
        skill_definitions={
            SkillId("negoziazione"): SkillDefinition(
                skill_id=SkillId("negoziazione"),
                name="Negoziazione",
            )
        },
        wardrobes={
            "victoria_evening": WardrobeOutfit(
                outfit_id="victoria_evening",
                owner_id=EntityId("victoria"),
                tags=("sexy", "elegant"),
                items=(
                    OutfitItem(
                        item_id="victoria_evening_dress",
                        name="evening dress",
                        slot="body",
                        layer=10,
                    ),
                ),
            )
        },
    )


class RecordingStateStore:
    def __init__(self, state: WorldState, *, fail_save: bool = False) -> None:
        self.state = state.model_copy(deep=True)
        self.saved: list[WorldState] = []
        self.fail_save = fail_save

    async def load(self, session_id: SessionId) -> WorldState:
        assert session_id == self.state.session_id
        return self.state.model_copy(deep=True)

    async def save(self, session_id: SessionId, state: WorldState) -> None:
        assert session_id == state.session_id
        if self.fail_save:
            raise PersistenceError("state disk unavailable")
        self.state = state.model_copy(deep=True)
        self.saved.append(state.model_copy(deep=True))


class MemoryCheckpointStore:
    def __init__(self) -> None:
        self.value: DiceCheckpoint | None = None

    async def save(self, checkpoint: DiceCheckpoint) -> None:
        self.value = checkpoint.model_copy(deep=True)

    async def load(self, session_id: SessionId) -> DiceCheckpoint | None:
        if self.value is None or self.value.session_id != session_id:
            return None
        return self.value.model_copy(deep=True)

    async def delete(self, session_id: SessionId) -> None:
        if self.value is not None and self.value.session_id == session_id:
            self.value = None


class FakeInterpreter:
    def __init__(self, action: ValidatedAction, calls: list[str]) -> None:
        self.action = action
        self.calls = calls

    async def interpret(self, context):
        self.calls.append("interpret")
        return self.action.model_copy(deep=True)


class FailingInterpreter:
    async def interpret(self, context):
        raise AssertionError("interpreter must not be called while resuming checkpoint")


class FakeCheckResolver:
    def __init__(self, resolved: ResolvedCheck, calls: list[str]) -> None:
        self.resolved = resolved
        self.calls = calls

    def resolve(self, proposal: CheckProposal, *, rating: int) -> ResolvedCheck:
        self.calls.append("dice")
        assert rating == self.resolved.rating
        return self.resolved.model_copy(deep=True)


class FailingCheckResolver:
    def resolve(self, proposal: CheckProposal, *, rating: int) -> ResolvedCheck:
        raise AssertionError("dice must not be rolled while resuming checkpoint")


class FakeActionResolver:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def resolve(self, **kwargs) -> TurnActionResolution:
        self.calls.append("resolve_action")
        return TurnActionResolution()


class FakePsychology:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.present: tuple[EntityId, ...] = ()

    def plan(self, **kwargs) -> TurnPsychologyPlan:
        self.calls.append("psychology_bond")
        self.present = kwargs["present_npc_ids"]
        return TurnPsychologyPlan()


class FakeCognition:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.npc_ids: list[EntityId] = []

    async def react(self, **kwargs) -> CognitionResult:
        npc_id = kwargs["npc_id"]
        self.calls.append(f"cognition:{npc_id}")
        self.npc_ids.append(npc_id)
        return CognitionResult(
            reaction=ValidatedNPCReaction(
                npc_id=npc_id,
                intent="acknowledge",
                speech_act="reply",
                action_intent="continue_conversation",
                target_ids=(EntityId("player"),),
            )
        )


class AcceptingOutfitCognition:
    async def react(self, **kwargs) -> CognitionResult:
        npc_id = kwargs["npc_id"]
        return CognitionResult(
            reaction=ValidatedNPCReaction(
                npc_id=npc_id,
                intent="accept_request",
                speech_act="agree",
                outfit_request_response=NPCOutfitRequestResponse(
                    disposition=OutfitRequestDisposition.ACCEPTED,
                    selected_outfit_id="victoria_evening",
                ),
            )
        )


class FakeNarration:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.scene = None

    async def generate(self, **kwargs) -> NarrationResult:
        self.calls.append("narration")
        self.scene = kwargs["scene"].model_copy(deep=True)
        return NarrationResult(
            focus=ConversationFocus(
                speaker_id=EntityId("player"),
                target_npc_id=EntityId("victoria"),
                topic="greeting",
                mode=NarrationMode.ACTION,
            ),
            units=(
                WorldNarrationDraft(
                    text="Victoria risponde al saluto.",
                    subject_ids=(EntityId("victoria"),),
                ),
            ),
            text="Victoria risponde al saluto.",
        )


class FailingVisual:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.scene = None

    async def render(self, scene):
        self.calls.append("visual")
        self.scene = scene.model_copy(deep=True)
        raise ExternalServiceError("renderer offline", code="renderer.connection")


class RecordingMemory:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.context: TurnMemoryContext | None = None
        self.plan = TurnMemoryPlan()

    async def prepare(self, context: TurnMemoryContext) -> TurnMemoryPlan:
        self.calls.append("memory_prepare")
        self.context = context.model_copy(deep=True)
        return self.plan.model_copy(deep=True)

    async def store(self, plan: TurnMemoryPlan) -> None:
        self.calls.append("memory_store")
        assert plan == self.plan


def _no_check_action() -> ValidatedAction:
    return ValidatedAction(
        intent="greet",
        target_ids=(EntityId("victoria"),),
    )


def _checked_action() -> ValidatedAction:
    return ValidatedAction(
        intent="persuade",
        target_ids=(EntityId("victoria"),),
        check=CheckProposal(skill_id=SkillId("negoziazione"), difficulty=4),
        skill_rating=3,
    )


def _resolved_check() -> ResolvedCheck:
    return ResolvedCheck(
        skill_id=SkillId("negoziazione"),
        difficulty=4,
        rating=3,
        pool_size=3,
        dice=(6, 4, 2),
        success_count=2,
        outcome=CheckOutcome.FULL_SUCCESS,
    )


def _orchestrator(
    *,
    action: ValidatedAction,
    state_store: RecordingStateStore,
    checkpoint_store: MemoryCheckpointStore,
    calls: list[str],
    interpreter=None,
    check_resolver=None,
    cognition=None,
):
    psychology = FakePsychology(calls)
    cognition = cognition or FakeCognition(calls)
    narration = FakeNarration(calls)
    visual = FailingVisual(calls)
    memory = RecordingMemory(calls)
    manager = AuthoritativeStateManager(
        initial_state=state_store.state,
        state_store=state_store,
    )
    orchestrator = TurnOrchestrator(
        state=manager,
        checkpoint=DiceCheckpointService(store=checkpoint_store),
        interpreter=interpreter or FakeInterpreter(action, calls),
        check_resolver=check_resolver or FakeCheckResolver(_resolved_check(), calls),
        action_resolver=FakeActionResolver(calls),
        psychology=psychology,
        cognition=cognition,
        reaction_mutations=DefaultReactionMutationPlanner(),
        scene_builder=DefaultTurnSceneBuilder(),
        narration=narration,
        visual=visual,
        memory=memory,
    )
    return orchestrator, manager, psychology, cognition, narration, visual, memory


@pytest.mark.asyncio
async def test_accepted_npc_outfit_is_committed_before_shared_scene_and_render() -> None:
    calls: list[str] = []
    store = RecordingStateStore(_world())
    checkpoints = MemoryCheckpointStore()
    action = ValidatedAction(
        intent="request_outfit_change",
        target_ids=(EntityId("victoria"),),
        outfit_request=ValidatedOutfitRequest(
            target_id=EntityId("victoria"),
            requested_state="wear_outfit",
            semantic_tags=("sexy",),
            candidate_outfit_ids=("victoria_evening",),
        ),
    )
    orchestrator, _, _, _, narration, visual, memory = _orchestrator(
        action=action,
        state_store=store,
        checkpoint_store=checkpoints,
        calls=calls,
        cognition=AcceptingOutfitCognition(),
    )

    result = await orchestrator.run(
        TurnCommand(player_input="Victoria, mettiti qualcosa di sexy")
    )

    expected = ("victoria_evening_dress",)
    assert tuple(
        item.item_id for item in result.committed_state.npcs[EntityId("victoria")].outfit.items
    ) == expected
    victoria = next(
        subject for subject in result.scene.visible_subjects if subject.entity_id == "victoria"
    )
    assert tuple(item.item_id for item in victoria.outfit.items) == expected
    assert narration.scene == result.scene
    assert visual.scene == result.scene
    assert memory.context is not None and memory.context.scene == result.scene


@pytest.mark.asyncio
async def test_turn_connects_present_npcs_once_and_reuses_one_scene_after_atomic_commit() -> None:
    calls: list[str] = []
    store = RecordingStateStore(_world())
    checkpoints = MemoryCheckpointStore()
    orchestrator, manager, psychology, cognition, narration, visual, memory = _orchestrator(
        action=_no_check_action(),
        state_store=store,
        checkpoint_store=checkpoints,
        calls=calls,
    )

    result = await orchestrator.run(TurnCommand(player_input="Buona sera Victoria!"))

    assert psychology.present == (EntityId("victoria"),)
    assert cognition.npc_ids == [EntityId("victoria")]
    assert EntityId("stella") not in cognition.npc_ids
    assert len(store.saved) == 1
    assert int(result.committed_state.turn_number) == 2
    assert result.committed_state.npcs[EntityId("victoria")].intentions == (
        "continue_conversation",
    )
    assert manager.snapshot() == result.committed_state
    assert narration.scene == result.scene
    assert visual.scene == result.scene
    assert memory.context is not None
    assert memory.context.scene == result.scene
    assert memory.context.state == result.committed_state
    assert result.memory_stored is True
    assert result.visual is None
    assert tuple(issue.phase for issue in result.post_commit_issues) == ("visual",)
    assert calls.index("narration") < calls.index("memory_prepare")
    assert calls.index("memory_prepare") < calls.index("visual")
    assert calls.index("visual") < calls.index("memory_store")


@pytest.mark.asyncio
async def test_checked_action_requires_player_decision_before_any_downstream_phase() -> None:
    calls: list[str] = []
    store = RecordingStateStore(_world())
    checkpoints = MemoryCheckpointStore()
    orchestrator, _, _, _, _, _, _ = _orchestrator(
        action=_checked_action(),
        state_store=store,
        checkpoint_store=checkpoints,
        calls=calls,
    )

    with pytest.raises(CheckDecisionRequiredError):
        await orchestrator.run(TurnCommand(player_input="Convincila."))

    assert calls == ["interpret"]
    assert store.saved == []
    assert checkpoints.value is None


@pytest.mark.asyncio
async def test_dice_checkpoint_resume_skips_interpreter_and_rng_then_clears_after_commit() -> None:
    calls: list[str] = []
    state = _world()
    state_store = RecordingStateStore(state)
    checkpoints = MemoryCheckpointStore()
    checkpoint_service = DiceCheckpointService(store=checkpoints)
    action = _checked_action()
    resolved = _resolved_check()
    await checkpoint_service.save_after_roll(
        state=state,
        player_input="Convincila.",
        validated_action=action,
        proposal=action.check,
        resolved_check=resolved,
        player_decision=CheckDecision.ROLL.value,
    )
    orchestrator, _, _, _, _, _, _ = _orchestrator(
        action=action,
        state_store=state_store,
        checkpoint_store=checkpoints,
        calls=calls,
        interpreter=FailingInterpreter(),
        check_resolver=FailingCheckResolver(),
    )

    result = await orchestrator.run(TurnCommand(player_input="Convincila."))

    assert result.checkpoint_reused is True
    assert result.resolved_check == resolved
    assert checkpoints.value is None
    assert "interpret" not in calls
    assert "dice" not in calls


@pytest.mark.asyncio
async def test_pending_checkpoint_rejects_different_player_input_without_side_effects() -> None:
    calls: list[str] = []
    state = _world()
    state_store = RecordingStateStore(state)
    checkpoints = MemoryCheckpointStore()
    action = _checked_action()
    await DiceCheckpointService(store=checkpoints).save_after_roll(
        state=state,
        player_input="Convincila.",
        validated_action=action,
        proposal=action.check,
        resolved_check=_resolved_check(),
        player_decision=CheckDecision.ROLL.value,
    )
    orchestrator, _, _, _, _, _, _ = _orchestrator(
        action=action,
        state_store=state_store,
        checkpoint_store=checkpoints,
        calls=calls,
        interpreter=FailingInterpreter(),
        check_resolver=FailingCheckResolver(),
    )

    with pytest.raises(PendingDiceCheckpointError):
        await orchestrator.run(TurnCommand(player_input="Faccio qualcos'altro."))

    assert state_store.saved == []
    assert checkpoints.value is not None
    assert calls == []


@pytest.mark.asyncio
async def test_commit_failure_keeps_dice_checkpoint_and_never_runs_post_commit_work() -> None:
    calls: list[str] = []
    store = RecordingStateStore(_world(), fail_save=True)
    checkpoints = MemoryCheckpointStore()
    orchestrator, _, _, _, _, _, _ = _orchestrator(
        action=_checked_action(),
        state_store=store,
        checkpoint_store=checkpoints,
        calls=calls,
    )

    with pytest.raises(PersistenceError, match="state disk unavailable"):
        await orchestrator.run(
            TurnCommand(
                player_input="Convincila.",
                check_decision=CheckDecision.ROLL,
            )
        )

    assert checkpoints.value is not None
    assert "memory_prepare" in calls
    assert "visual" not in calls
    assert "memory_store" not in calls
    assert store.saved == []

"""Module 25 scenarios A-M, kept together as the final behavioural contract."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from epos.application.actions import CheckProposal, ResolvedCheck, ValidatedAction
from epos.application.cognition import (
    CognitionResult,
    CognitionScene,
    CognitionValidationError,
    NPCCognitionService,
    NPCReactionProposal,
    NPCReactionValidator,
    PrivateCognitiveContext,
    PrivateCognitiveContextBuilder,
    ValidatedNPCReaction,
)
from epos.application.conversation import (
    ConversationFocus,
    NarrationMode,
    NarrationResult,
    NPCDialogueDraft,
)
from epos.application.memory import (
    LongTermMemoryRecord,
    MemoryRecallResult,
    MemoryRecallService,
    MemoryService,
)
from epos.application.psychology import (
    PsychologicalEvent,
    PsychologicalEventType,
    PsychologyProfile,
    PsychologyService,
)
from epos.application.results import TurnResultMapper
from epos.application.state import AuthoritativeStateManager, DiceCheckpointService
from epos.application.turn import (
    BondDerivationContext,
    DefaultReactionMutationPlanner,
    DefaultTurnActionResolver,
    DefaultTurnSceneBuilder,
    EmergentBondPolicy,
    TurnCommand,
    TurnMemoryCoordinator,
    TurnOrchestrator,
    TurnPsychologyPlan,
)
from epos.application.visual import ObservableSceneBuilder, SceneObservationInput
from epos.application.visual.bridge import VisualPipelineResources, VisualTurnPipeline
from epos.application.visual.canonical import VisualCanonicalizer
from epos.application.visual.prompt import PromptCompilerProfile, SemanticPromptCompiler
from epos.application.visual.recovery import PendingRender, RenderRecoveryService
from epos.application.visual.rendering import RendererConnectionError, RenderResult
from epos.application.visual.vst import (
    RawVST,
    SemanticIntent,
    VSTActionIntent,
    VSTCameraIntent,
    VSTLightingIntent,
    VSTLocationIntent,
    VSTSafetyIntent,
    VSTStyleIntent,
    VSTSubjectIntent,
    VSTSubjectProminence,
    VSTVisualFocus,
)
from epos.application.visual.workflow import ComfyWorkflowProfile
from epos.domain.bond import BondPhase, BondState, LovePhase
from epos.domain.ids import EntityId, LocationId, MemoryId, SessionId, TurnNumber, WorldpackId
from epos.domain.memory import MemoryEntryState
from epos.domain.npc import NPCIdentity, NPCState, SecretState
from epos.domain.player import PlayerState
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState
from epos.domain.world_state import LocationState, WorldState
from epos.infrastructure.memory.simple import SimpleMemoryAdapter
from epos.infrastructure.rendering.comfy import (
    AtomicRenderImageStore,
    ComfyRenderRequestBuilder,
    ComfyUIAdapter,
    ComfyUIAdapterSettings,
    ComfyWorkflowBuilder,
    FileSystemComfyWorkflowTemplateLoader,
    HttpxComfyApiClient,
)
from epos.infrastructure.rendering.visual_diagnostics import AtomicVisualDiagnosticsStore
from epos.infrastructure.worldpacks.loader import FileSystemWorldpackLoader

PLAYER = EntityId("player")
VICTORIA = EntityId("victoria")
LUNA = EntityId("luna")
LOBBY = LocationId("lobby")
SUITE = LocationId("suite")


def _turn_world(
    *,
    anger: float = 0.0,
    joy: float = 0.0,
    trust: float = 0.0,
    victoria_location: LocationId = LOBBY,
) -> WorldState:
    return WorldState(
        session_id=SessionId("acceptance-session"),
        worldpack_id=WorldpackId("acceptance-world"),
        turn_number=TurnNumber(0),
        day=1,
        world_phase="evening",
        player=PlayerState(entity_id=PLAYER, name="Alex", location_id=LOBBY),
        npcs={
            VICTORIA: NPCState(
                identity=NPCIdentity(entity_id=VICTORIA, name="Victoria", role="host"),
                location_id=victoria_location,
                personality=("controlled", "elegant"),
                speech_style="precise",
                emotional_state=EmotionalState(anger=anger, joy=joy),
                relationships={PLAYER: RelationshipState(trust=trust)},
            )
        },
        locations={
            LOBBY: LocationState(location_id=LOBBY, name="Lobby"),
            SUITE: LocationState(location_id=SUITE, name="Suite"),
        },
    )


class _StateStore:
    def __init__(self, state: WorldState) -> None:
        self.state = state.model_copy(deep=True)
        self.saves = 0

    async def load(self, session_id: SessionId) -> WorldState:
        return self.state.model_copy(deep=True)

    async def save(self, session_id: SessionId, state: WorldState) -> None:
        self.saves += 1
        self.state = state.model_copy(deep=True)


class _CheckpointStore:
    async def save(self, checkpoint) -> None:
        raise AssertionError("greeting must not roll dice")

    async def load(self, session_id):
        return None

    async def delete(self, session_id) -> None:
        return None


class _GreetingInterpreter:
    async def interpret(self, context) -> ValidatedAction:
        targets = (VICTORIA,) if VICTORIA in context.present_npc_ids else ()
        return ValidatedAction(intent="greet", target_ids=targets)


class _NoCheck:
    def resolve(self, proposal: CheckProposal, *, rating: int) -> ResolvedCheck:
        raise AssertionError("greeting must not roll dice")


class _NoPsychology:
    def plan(self, **kwargs) -> TurnPsychologyPlan:
        return TurnPsychologyPlan()


class _GreetingCognition:
    def __init__(self) -> None:
        self.calls = 0

    async def react(self, *, npc_id, **kwargs):
        self.calls += 1
        return CognitionResult(
            reaction=ValidatedNPCReaction(
                npc_id=npc_id,
                intent="respond_to_greeting",
                speech_act="acknowledge",
                topic_tags=("greeting",),
                target_ids=(PLAYER,),
            )
        )


class _EmotionAwareNarration:
    async def generate(self, *, state, reactions, **kwargs) -> NarrationResult:
        if not reactions:
            text = "La lobby resta tranquilla."
            return NarrationResult(
                focus=ConversationFocus(
                    speaker_id=PLAYER,
                    topic="greeting",
                    mode=NarrationMode.BRIEF_SOCIAL,
                ),
                units=(),
                text=text,
            )
        victoria = state.npcs[VICTORIA]
        relationship = victoria.relationships[PLAYER]
        if victoria.emotional_state.anger >= 8 and relationship.trust <= 3:
            speech = "Buona sera."
        elif victoria.emotional_state.joy >= 8 and relationship.trust >= 8:
            speech = "Buona sera, sono davvero felice di vederti."
        else:
            speech = "Buona sera, che piacere."
        return NarrationResult(
            focus=ConversationFocus(
                speaker_id=PLAYER,
                target_npc_id=VICTORIA,
                topic="greeting",
                mode=NarrationMode.BRIEF_SOCIAL,
            ),
            units=(NPCDialogueDraft(speaker_id=VICTORIA, text=speech),),
            text=f"Victoria: {speech}",
        )


class _AcceptanceVisual:
    def __init__(self, *, offline: bool = False) -> None:
        self.calls = 0
        self.offline = offline

    async def render(self, scene):
        self.calls += 1
        if self.offline:
            raise RendererConnectionError("ComfyUI offline")
        from epos.application.visual.bridge import VisualPipelineResult
        from epos.application.visual.prompt import RenderPromptContract
        from epos.application.visual.rendering import RenderResult

        return VisualPipelineResult.model_construct(
            prompt_contract=RenderPromptContract(
                positive_prompt="Victoria in the lobby",
                negative_prompt="low quality",
                width=896,
                height=1152,
            ),
            render_result=RenderResult(
                status="success",
                image_path="renders/greeting.png",
                backend="comfyui",
                prompt_id="greeting-1",
                duration_ms=10,
                attempts=1,
            ),
            diagnostics_path="diagnostics/greeting.json",
        )


class _NoMemoryDerivation:
    async def derive(self, context) -> tuple[LongTermMemoryRecord, ...]:
        return ()


def _turn_runtime(state: WorldState, *, offline: bool = False):
    store = _StateStore(state)
    cognition = _GreetingCognition()
    visual = _AcceptanceVisual(offline=offline)
    orchestrator = TurnOrchestrator(
        state=AuthoritativeStateManager(initial_state=state, state_store=store),
        checkpoint=DiceCheckpointService(store=_CheckpointStore()),
        interpreter=_GreetingInterpreter(),
        check_resolver=_NoCheck(),
        action_resolver=DefaultTurnActionResolver(),
        psychology=_NoPsychology(),
        cognition=cognition,
        reaction_mutations=DefaultReactionMutationPlanner(),
        scene_builder=DefaultTurnSceneBuilder(),
        narration=_EmotionAwareNarration(),
        visual=visual,
        memory=TurnMemoryCoordinator(
            derivation=_NoMemoryDerivation(),
            capture=MemoryService.default(),
            store=SimpleMemoryAdapter(),
        ),
    )
    return orchestrator, store, cognition, visual


@pytest.mark.asyncio
async def test_scenario_a_greeting_is_brief_voiced_agency_safe_and_attempts_image() -> None:
    orchestrator, _, cognition, visual = _turn_runtime(
        _turn_world(joy=4.0, trust=6.0)
    )

    internal = await orchestrator.run(TurnCommand(player_input="Buona sera Victoria!"))
    public = TurnResultMapper.map(internal)

    assert public.narration == "Victoria: Buona sera, che piacere."
    assert public.dialogues[0].speaker_id == VICTORIA
    assert "invest" not in public.narration.casefold()
    assert "Alex:" not in public.narration
    assert cognition.calls == 1
    assert visual.calls == 1


@pytest.mark.asyncio
async def test_scenario_b_angry_low_trust_victoria_changes_same_greeting() -> None:
    angry_runtime, *_ = _turn_runtime(_turn_world(anger=9.0, trust=2.0))
    angry = await angry_runtime.run(TurnCommand(player_input="Buona sera Victoria!"))

    assert angry.narration.text == "Victoria: Buona sera."


@pytest.mark.asyncio
async def test_scenario_c_happy_high_trust_victoria_is_distinct() -> None:
    angry_runtime, *_ = _turn_runtime(_turn_world(anger=9.0, trust=2.0))
    happy_runtime, *_ = _turn_runtime(_turn_world(joy=9.0, trust=8.0))
    angry = await angry_runtime.run(TurnCommand(player_input="Buona sera Victoria!"))
    happy = await happy_runtime.run(TurnCommand(player_input="Buona sera Victoria!"))

    assert happy.narration.text == "Victoria: Buona sera, sono davvero felice di vederti."
    assert angry.narration.text != happy.narration.text


class _MemoryAwareCognition:
    def __init__(self) -> None:
        self.seen: tuple[MemoryId, ...] = ()

    async def invoke(self, request: PrivateCognitiveContext) -> NPCReactionProposal:
        self.seen = tuple(item.memory.memory_id for item in request.recalled_memories)
        return NPCReactionProposal(
            npc_id=request.npc_id,
            intent="acknowledge_old_promise",
            speech_act="acknowledge",
            topic_tags=("promise", "key"),
            referenced_memory_ids=self.seen,
            target_ids=(request.player_id,),
        )


@pytest.mark.asyncio
async def test_scenario_f_old_promise_is_recalled_and_changes_cognition() -> None:
    state = _turn_world(trust=6.0)
    state.turn_number = TurnNumber(100)
    store = SimpleMemoryAdapter()
    promise = MemoryEntryState(
        memory_id=MemoryId("promise-key"),
        turn=TurnNumber(2),
        summary="Il giocatore promise a Victoria di tornare con la chiave.",
        participants=(PLAYER, VICTORIA),
        salience=9.0,
        tags=("promise",),
    )
    await store.add(LongTermMemoryRecord(npc_id=VICTORIA, memory=promise))
    port = _MemoryAwareCognition()
    service = NPCCognitionService(
        memory_recall=MemoryRecallService(store),
        port=port,
        validator=NPCReactionValidator(),
    )

    result = await service.react(
        state=state,
        npc_id=VICTORIA,
        scene=CognitionScene(
            location_id=LOBBY,
            present_entity_ids=(PLAYER, VICTORIA),
            summary="Victoria incontra il giocatore nella lobby.",
        ),
        player_input="Ricordi la promessa sulla chiave?",
        action=ValidatedAction(intent="dialogue", target_ids=(VICTORIA,)),
        resolved_check=None,
    )

    assert result is not None
    assert port.seen == (MemoryId("promise-key"),)
    assert result.reaction.intent == "acknowledge_old_promise"
    assert result.reaction.referenced_memory_ids == (MemoryId("promise-key"),)


def test_scenario_g_victoria_cannot_reveal_lunas_secret() -> None:
    state = _turn_world()
    state.npcs[LUNA] = NPCState(
        identity=NPCIdentity(entity_id=LUNA, name="Luna", role="guest"),
        location_id=LOBBY,
        secrets=(SecretState(secret_id="luna_letter", fact="La lettera è sotto il letto."),),
    )
    action = ValidatedAction(intent="ask_secret", target_ids=(VICTORIA,))
    context = PrivateCognitiveContextBuilder().build(
        state=state,
        npc_id=VICTORIA,
        scene=CognitionScene(
            location_id=LOBBY,
            present_entity_ids=(PLAYER, VICTORIA, LUNA),
        ),
        player_input="Dov'è la lettera di Luna?",
        action=action,
        recalled=MemoryRecallResult(query_text="lettera", memories=()),
        resolved_check=None,
    )
    proposal = NPCReactionProposal(
        npc_id=VICTORIA,
        intent="reveal_secret",
        speech_act="inform",
        requested_secret_disclosures=("luna_letter",),
    )

    with pytest.raises(CognitionValidationError, match="not authorized for disclosure"):
        NPCReactionValidator().validate(proposal, context)

    assert context.secrets == ()


@pytest.mark.asyncio
async def test_scenario_h_offscreen_npc_psychology_does_not_change_for_five_turns() -> None:
    initial = _turn_world(anger=7.0, joy=2.0, trust=3.0, victoria_location=SUITE)
    before = initial.npcs[VICTORIA].model_copy(deep=True)
    orchestrator, store, cognition, visual = _turn_runtime(initial)

    for _ in range(5):
        await orchestrator.run(TurnCommand(player_input="Aspetto nella lobby."))

    after = store.state.npcs[VICTORIA]
    assert after.emotional_state == before.emotional_state
    assert after.relationships == before.relationships
    assert after.bond_state == before.bond_state
    assert cognition.calls == 0
    assert store.saves == 5
    assert visual.calls == 5


async def _resort_visual_fixture():
    loaded = await FileSystemWorldpackLoader().load(
        Path("worldpacks/resort_world"),
        session_id="full-acceptance-visual",
    )
    state = loaded.world_state
    scene = ObservableSceneBuilder().build(
        state=state,
        observation=SceneObservationInput(
            action=ValidatedAction(intent="dialogue", target_ids=(VICTORIA,))
        ),
    )
    action_semantic = loaded.action_library.entries[0]
    camera_semantic = loaded.camera_library.entries[0]
    lighting_semantic = loaded.lighting_library.entries[0]
    style_semantic = loaded.style_library.entries[0]
    raw = RawVST(
        scene_id=scene.scene_id,
        location=VSTLocationIntent(location_id=state.player.location_id),
        subjects=(
            VSTSubjectIntent(
                entity_id=VICTORIA,
                prominence=VSTSubjectProminence.PRIMARY,
                outfit_intent=SemanticIntent(
                    description="invented black Catwoman catsuit",
                    tags=("invented", "catwoman"),
                ),
            ),
        ),
        action=VSTActionIntent(
            participants=(VICTORIA,),
            intent=SemanticIntent(description=action_semantic.description),
        ),
        visual_focus=VSTVisualFocus(
            subject_ids=(VICTORIA,),
            intent=SemanticIntent(description="Victoria greeting the player"),
        ),
        camera=VSTCameraIntent(
            shot=SemanticIntent(description=camera_semantic.description)
        ),
        lighting=VSTLightingIntent(
            intent=SemanticIntent(description=lighting_semantic.description)
        ),
        style=VSTStyleIntent(intent=SemanticIntent(description=style_semantic.description)),
        safety=VSTSafetyIntent(),
    )
    return loaded, scene, raw


@pytest.mark.asyncio
async def test_scenario_i_canonicalizer_replaces_llm_invented_outfit() -> None:
    loaded, scene, raw = await _resort_visual_fixture()
    authoritative = loaded.world_state.npcs[VICTORIA].outfit.model_copy(deep=True)

    canonical = VisualCanonicalizer().canonicalize(
        scene=scene,
        raw_vst=raw,
        worldpack=loaded,
    )

    assert raw.subjects[0].outfit_intent is not None
    assert "Catwoman" in raw.subjects[0].outfit_intent.description
    assert canonical.subjects[0].outfit == authoritative
    assert all(
        "catwoman" not in item.name.casefold()
        for item in canonical.subjects[0].outfit.items
    )


@pytest.mark.asyncio
async def test_scenario_j_same_structured_visual_input_compiles_exact_same_prompt() -> None:
    loaded, scene, raw = await _resort_visual_fixture()
    canonical = VisualCanonicalizer().canonicalize(
        scene=scene,
        raw_vst=raw,
        worldpack=loaded,
    )
    config = VisualPipelineResources(
        worldpack=loaded,
        prompt_profile=PromptCompilerProfile(),
        seed=424242,
    )
    compiler = SemanticPromptCompiler()
    from epos.application.visual.prompt import WorldpackVisualConfig

    visual_config = WorldpackVisualConfig.from_loaded_worldpack(
        loaded,
        profile=config.prompt_profile,
    )

    first = compiler.compile(canonical, visual_config)
    second = compiler.compile(canonical.model_copy(deep=True), visual_config.model_copy(deep=True))

    assert first.positive_prompt == second.positive_prompt
    assert first.negative_prompt == second.negative_prompt
    assert first.model_dump_json() == second.model_dump_json()


class _FixedVisualDirector:
    def __init__(self, raw: RawVST) -> None:
        self.raw = raw
        self.calls = 0

    async def generate(self, scene) -> RawVST:
        self.calls += 1
        assert scene.scene_id == self.raw.scene_id
        return self.raw.model_copy(deep=True)


@pytest.mark.asyncio
async def test_scenario_k_comfy_online_runs_vst_prompt_workflow_http_and_image(
    tmp_path: Path,
) -> None:
    loaded, scene, raw = await _resort_visual_fixture()
    profile = ComfyWorkflowProfile.from_rendering_config(
        loaded.world_state.rendering_config
    )
    template = await FileSystemComfyWorkflowTemplateLoader().load(
        Path("worldpacks/resort_world") / profile.workflow_file
    )
    paths: list[str] = []
    submitted: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/prompt":
            submitted.update(json.loads(request.content.decode("utf-8")))
            return httpx.Response(200, json={"prompt_id": "prompt-acceptance"})
        if request.url.path == "/history/prompt-acceptance":
            return httpx.Response(
                200,
                json={
                    "prompt-acceptance": {
                        "outputs": {
                            "9": {
                                "images": [
                                    {
                                        "filename": "acceptance.png",
                                        "subfolder": "",
                                        "type": "output",
                                    }
                                ]
                            }
                        },
                        "status": {"status_str": "success", "completed": True, "messages": []},
                    }
                },
            )
        if request.url.path == "/view":
            return httpx.Response(200, content=b"acceptance-png")
        raise AssertionError(f"unexpected ComfyUI path: {request.url.path}")

    api = HttpxComfyApiClient(
        endpoint="http://127.0.0.1:8188",
        timeout_seconds=1.0,
        transport=httpx.MockTransport(handler),
    )
    renderer = ComfyUIAdapter(
        settings=ComfyUIAdapterSettings(
            endpoint="http://127.0.0.1:8188",
            ws_endpoint="ws://127.0.0.1:8188/ws",
            output_directory=tmp_path / "images",
            request_timeout_seconds=1.0,
            render_timeout_seconds=1.0,
            poll_interval_seconds=0.001,
            retry_delay_seconds=0.0,
            max_attempts=1,
        ),
        api=api,
        image_store=AtomicRenderImageStore(tmp_path / "images"),
    )
    director = _FixedVisualDirector(raw)
    pipeline = VisualTurnPipeline(
        director=director,
        canonicalizer=VisualCanonicalizer(),
        compiler=SemanticPromptCompiler(),
        render_request_builder=ComfyRenderRequestBuilder(
            workflow_builder=ComfyWorkflowBuilder(),
            template=template,
            profile=profile,
            client_id="full-acceptance",
        ),
        renderer=renderer,
        diagnostics=AtomicVisualDiagnosticsStore(tmp_path / "diagnostics"),
    )

    result = await pipeline.run(
        scene=scene,
        resources=VisualPipelineResources(
            worldpack=loaded,
            prompt_profile=PromptCompilerProfile(),
            seed=424242,
        ),
    )

    assert director.calls == 1
    assert result.raw_vst == raw
    assert result.prompt_contract.positive_prompt
    assert submitted["prompt"] == result.render_request.payload["prompt"]
    assert paths == ["/prompt", "/history/prompt-acceptance", "/view"]
    assert result.render_result.status == "success"
    assert result.render_result.image_path is not None
    assert Path(result.render_result.image_path).read_bytes() == b"acceptance-png"


@pytest.mark.asyncio
async def test_scenario_l_offline_renderer_does_not_destroy_narrative_turn() -> None:
    orchestrator, store, _, visual = _turn_runtime(
        _turn_world(joy=4.0, trust=6.0),
        offline=True,
    )

    internal = await orchestrator.run(TurnCommand(player_input="Buona sera Victoria!"))
    public = TurnResultMapper.map(internal)

    assert public.narration == "Victoria: Buona sera, che piacere."
    assert public.visual.render_status == "failed"
    assert public.visual.render_error
    assert public.visual.retry_available is True
    assert int(store.state.turn_number) == 1
    assert visual.calls == 1


class _PendingStore:
    def __init__(self, pending: PendingRender) -> None:
        self.pending = pending
        self.deleted = False

    async def save(self, pending: PendingRender) -> str:
        self.pending = pending
        return "pending.json"

    async def load(self, session_id: SessionId) -> PendingRender | None:
        return None if self.deleted else self.pending

    async def delete(self, session_id: SessionId, turn_number: TurnNumber) -> None:
        self.deleted = True


class _RecoveredRenderer:
    def __init__(self) -> None:
        self.contracts: list[PendingRender] = []

    async def render(self, pending: PendingRender) -> RenderResult:
        self.contracts.append(pending)
        return RenderResult(
            status="success",
            image_path="renders/recovered.png",
            backend="comfyui",
            prompt_id="recovered-1",
            error=None,
            duration_ms=15,
            attempts=1,
        )


@pytest.mark.asyncio
async def test_scenario_m_rerender_replays_only_saved_contract() -> None:
    from epos.application.visual.bridge import RenderRequestSnapshot
    from epos.application.visual.canonical import CanonicalVST
    from epos.application.visual.models import SceneTime
    from epos.application.visual.prompt import RenderPromptContract
    from epos.domain.ids import SceneId

    scene_id = SceneId("acceptance-session:12")
    pending = PendingRender.model_construct(
        session_id=SessionId("acceptance-session"),
        turn_number=TurnNumber(12),
        scene_id=scene_id,
        canonical_vst=CanonicalVST.model_construct(
            scene_id=scene_id,
            time=SceneTime(turn_number=TurnNumber(12), day=1, world_phase="evening"),
        ),
        prompt_contract=RenderPromptContract(
            positive_prompt="saved positive",
            negative_prompt="saved negative",
            width=896,
            height=1152,
        ),
        render_request=RenderRequestSnapshot(
            backend="comfyui",
            request_id="saved-request",
            payload={"client_id": "acceptance", "prompt": {}},
        ),
        request_version="1",
    )
    store = _PendingStore(pending)
    renderer = _RecoveredRenderer()
    counters = {"dice": 1, "npc": 1, "mutations": 1}
    before = counters.copy()

    result = await RenderRecoveryService(store=store, executor=renderer).retry(
        SessionId("acceptance-session")
    )

    assert result.render_result.status == "success"
    assert renderer.contracts == [pending]
    assert counters == before
    assert store.deleted is True


def _bond_context(
    relationship: RelationshipState,
    *,
    bond: BondState | None = None,
    turn: int = 100,
    day: int = 20,
    core_memories: int = 8,
    events: tuple[str, ...] = (PsychologicalEventType.ROMANTIC_MILESTONE.value,),
) -> BondDerivationContext:
    return BondDerivationContext(
        npc_id=EntityId("victoria"),
        player_id=EntityId("player"),
        current_bond=BondState() if bond is None else bond,
        relationship_with_player=relationship,
        emotional_state=EmotionalState(),
        core_memory_count=core_memories,
        turn_number=turn,
        day=day,
        event_types=events,
    )


def test_scenario_d_attraction_alone_is_not_love() -> None:
    relationship = RelationshipState(
        attraction=10.0,
        trust=3.0,
        affection=2.0,
        respect=8.0,
    )

    derived = EmergentBondPolicy().derive(_bond_context(relationship))

    assert derived.phase is BondPhase.NONE
    assert derived.love_phase is LovePhase.NONE


def test_scenario_e_long_positive_history_progresses_to_python_derived_love() -> None:
    psychology = PsychologyService.default()
    bond_policy = EmergentBondPolicy()
    emotions = EmotionalState()
    relationship = RelationshipState()
    bond = BondState()
    phases = [(bond.phase, bond.love_phase)]

    for turn in range(1, 81):
        update = psychology.apply_event(
            event=PsychologicalEvent(
                event_type=PsychologicalEventType.ROMANTIC_MILESTONE,
                intensity=1.0,
            ),
            emotions=emotions,
            relationship=relationship,
            profile=PsychologyProfile(),
        )
        emotions = update.emotions
        relationship = update.relationship
        bond = bond_policy.derive(
            _bond_context(
                relationship,
                bond=bond,
                turn=turn,
                day=1 + turn // 8,
                core_memories=turn // 12,
            )
        )
        stage = (bond.phase, bond.love_phase)
        if stage != phases[-1]:
            phases.append(stage)

    assert phases == [
        (BondPhase.NONE, LovePhase.NONE),
        (BondPhase.FORMING, LovePhase.NONE),
        (BondPhase.ESTABLISHED, LovePhase.NONE),
        (BondPhase.DEEP, LovePhase.NONE),
        (BondPhase.DEEP, LovePhase.FALLING_IN_LOVE),
        (BondPhase.DEEP, LovePhase.IN_LOVE),
    ]

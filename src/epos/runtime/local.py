"""Concrete local composition root for the EPOS NEXT engine."""

from __future__ import annotations

import asyncio
import random
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx
import yaml

from epos.application.actions import (
    ActionInterpretation,
    ActionInterpreterContext,
    ActionInterpreterService,
    ActionValidator,
    CheckResolver,
    D6OutcomePolicy,
)
from epos.application.cognition import (
    NPCCognitionService,
    NPCReactionProposal,
    NPCReactionValidator,
    PrivateCognitiveContext,
)
from epos.application.conversation import (
    ConversationFocusContext,
    ConversationFocusProposal,
    ConversationFocusService,
    ConversationFocusValidator,
    NarrationAuditContext,
    NarrationAuditProposal,
    NarrationAuditValidator,
    NarrationContext,
    NarrationContextBuilder,
    NarrationProposal,
    NarrationService,
    NarrationValidator,
)
from epos.application.diagnostics import ComponentHealthView, RuntimeHealthView
from epos.application.memory import MemoryRecallService, MemoryService
from epos.application.psychology import PsychologyService
from epos.application.results import TurnResult, TurnResultMapper, TurnVisualLora, TurnVisualResult
from epos.application.state import AuthoritativeStateManager, DiceCheckpointService
from epos.application.turn import (
    DefaultReactionMutationPlanner,
    DefaultTurnActionResolver,
    DefaultTurnNarrationCoordinator,
    DefaultTurnSceneBuilder,
    EmergentBondPolicy,
    PythonTurnCheckResolver,
    PythonTurnPsychologyPlanner,
    TurnCommand,
    TurnMemoryCoordinator,
    TurnOrchestrator,
    VisualTurnPipelineAdapter,
)
from epos.application.visual.bridge import VisualTurnPipeline
from epos.application.visual.canonical import VisualCanonicalizer
from epos.application.visual.prompt import SemanticPromptCompiler
from epos.application.visual.recovery import RenderRecoveryService
from epos.application.visual.rendering import RendererPort
from epos.application.visual.vst import RawVST, VisualDirectorContext, VisualDirectorService
from epos.application.worldpacks import LoadedWorldpack
from epos.domain.errors import ConfigurationError, PersistenceError
from epos.domain.ids import SessionId, WorldpackId
from epos.infrastructure.llm import LLMProviderStatus, LLMTask, StructuredLLMPort
from epos.infrastructure.llm.runtime import LLMRuntime, build_llm_runtime_from_env
from epos.infrastructure.memory.simple import SimpleMemoryAdapter
from epos.infrastructure.persistence import (
    JsonFileCheckpointStore,
    JsonFileStateStore,
    JsonPendingRenderStore,
)
from epos.infrastructure.persistence.atomic_files import atomic_write_bytes
from epos.infrastructure.rendering.a1111 import (
    A1111AdapterSettings,
    A1111ForgeAdapter,
    A1111HTTPClient,
    A1111RenderProfile,
    A1111RenderRequest,
    A1111RenderRequestBuilder,
)
from epos.infrastructure.rendering.comfy.image_store import AtomicRenderImageStore
from epos.infrastructure.rendering.visual_diagnostics import AtomicVisualDiagnosticsStore
from epos.infrastructure.worldpacks import FileSystemWorldpackLoader
from epos.presentation.models import SessionView, WorldpackView
from epos.runtime.adapters import (
    A1111PendingRenderExecutor,
    DefaultPsychologyProfiles,
    DeterministicTurnMemoryDerivation,
    NoopPsychologicalEventSource,
    StaticVisualResources,
)
from epos.runtime.config import LocalRuntimeSettings, load_local_settings


@dataclass(slots=True)
class _SessionRuntime:
    loaded_worldpack: LoadedWorldpack
    state: AuthoritativeStateManager
    orchestrator: TurnOrchestrator
    recovery: RenderRecoveryService


class LocalEPOSRuntime:
    """Persistent local runtime shared by the desktop and HTTP presentation layers."""

    def __init__(
        self,
        *,
        settings: LocalRuntimeSettings,
        llm_runtime: LLMRuntime,
        renderer: RendererPort[A1111RenderRequest],
        llm_health_client: httpx.AsyncClient | None = None,
    ) -> None:
        if llm_runtime.startup_diagnostic.status is not LLMProviderStatus.CONFIGURED:
            raise ConfigurationError(llm_runtime.startup_diagnostic.detail)
        self._settings = settings
        self._llm_runtime = llm_runtime
        self._renderer = renderer
        self._renderer_settings = A1111AdapterSettings.from_env(
            output_directory=settings.data_directory / "renders",
            environ=settings.environment,
        )
        self._llm_health_client = llm_health_client
        self._sessions: dict[SessionId, _SessionRuntime] = {}
        self._current_session_id: SessionId | None = None
        self._session_lock = asyncio.Lock()

    async def create_session(self, worldpack_id: WorldpackId) -> SessionView:
        async with self._session_lock:
            session_id = SessionId(f"{worldpack_id}-{uuid.uuid4().hex[:12]}")
            loaded = await FileSystemWorldpackLoader().load(
                self._worldpack_path(worldpack_id),
                session_id=str(session_id),
            )
            store = self._state_store()
            await store.save(session_id, loaded.world_state)
            runtime = await self._compose(loaded=loaded, state_store=store)
            self._sessions[session_id] = runtime
            await self._select_session(session_id)
            return SessionView.from_world_state(runtime.state.snapshot())

    async def get_session(self, session_id: SessionId) -> SessionView:
        runtime = await self._require_session(session_id)
        return SessionView.from_world_state(runtime.state.snapshot())

    async def run_turn(self, session_id: SessionId, command: TurnCommand) -> TurnResult:
        runtime = await self._require_session(session_id)
        state = runtime.state.snapshot()
        enriched = command
        if not command.known_location_ids:
            enriched = command.model_copy(
                update={
                    "known_location_ids": tuple(
                        sorted(state.locations, key=str)
                    )
                }
            )
        result = await runtime.orchestrator.run(enriched)
        await self._select_session(session_id)
        return TurnResultMapper.map(result)

    async def advance(self, session_id: SessionId) -> SessionView:
        return await self.get_session(session_id)

    async def resume(self, session_id: SessionId) -> SessionView:
        async with self._session_lock:
            store = self._state_store()
            persisted = await store.load(session_id)
            loaded = await FileSystemWorldpackLoader().load(
                self._worldpack_path(persisted.worldpack_id),
                session_id=str(session_id),
            )
            loaded = loaded.model_copy(update={"world_state": persisted}, deep=True)
            runtime = await self._compose(loaded=loaded, state_store=store)
            self._sessions[session_id] = runtime
            await self._select_session(session_id)
            return SessionView.from_world_state(runtime.state.snapshot())

    async def rerender(self, session_id: SessionId) -> TurnVisualResult:
        runtime = await self._require_session(session_id)
        retried = await runtime.recovery.retry(session_id)
        prompt = retried.pending.prompt_contract
        rendered = retried.render_result
        return TurnVisualResult(
            vst_status="ok",
            positive_prompt=prompt.positive_prompt,
            negative_prompt=prompt.negative_prompt,
            loras=tuple(
                TurnVisualLora(
                    entity_id=lora.entity_id,
                    alias=lora.alias,
                    filename=lora.filename,
                )
                for lora in prompt.loras
            ),
            image_path=rendered.image_path,
            render_status=rendered.status,
            render_error=rendered.error,
            backend=rendered.backend,
            prompt_id=rendered.prompt_id,
            retry_available=rendered.status == "failed",
        )

    async def list_worldpacks(self) -> tuple[WorldpackView, ...]:
        roots = await asyncio.to_thread(
            lambda: tuple(
                sorted(
                    (
                        path
                        for path in self._settings.worldpacks_directory.iterdir()
                        if path.is_dir() and (path / "world.yaml").is_file()
                    ),
                    key=lambda path: path.name,
                )
            )
        )
        views: list[WorldpackView] = []
        for root in roots:
            raw = await asyncio.to_thread(
                yaml.safe_load,
                (root / "world.yaml").read_text(encoding="utf-8"),
            )
            if not isinstance(raw, dict):
                continue
            worldpack_id = raw.get("worldpack_id")
            title = raw.get("title")
            if isinstance(worldpack_id, str) and isinstance(title, str):
                views.append(
                    WorldpackView(worldpack_id=WorldpackId(worldpack_id), title=title)
                )
        return tuple(views)

    async def health(self) -> RuntimeHealthView:
        llm, renderer = await asyncio.gather(
            self._llm_health(),
            self._renderer.health_check(),
        )
        return RuntimeHealthView(
            llm=llm,
            renderer=ComponentHealthView(
                status="up" if renderer.renderer_available else "down",
                detail=renderer.error or renderer.backend_version,
            ),
            current_worldpack=(
                None
                if self._current_session_id is None
                else self._sessions[self._current_session_id]
                .state.snapshot()
                .worldpack_id
            ),
            current_session=self._current_session_id,
        )

    async def _llm_health(self) -> ComponentHealthView:
        diagnostic = self._llm_runtime.startup_diagnostic
        if diagnostic.provider is None or diagnostic.model is None:
            return ComponentHealthView(status="down", detail=diagnostic.detail)
        if diagnostic.provider.value != "openai":
            return ComponentHealthView(
                status="unknown",
                detail=f"{diagnostic.provider.value}:{diagnostic.model} configured",
            )

        values = self._settings.environment
        base_url = values.get("EPOS_PRIMARY_LLM_BASE_URL", "").strip().rstrip("/")
        key_env = values.get("EPOS_PRIMARY_LLM_KEY_ENV", "").strip()
        api_key = values.get(key_env, "").strip()
        url = f"{base_url}/models/{quote(diagnostic.model, safe='')}"
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            if self._llm_health_client is not None:
                response = await self._llm_health_client.get(url, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            return ComponentHealthView(
                status="down",
                detail=f"OpenAI connection failed: {type(exc).__name__}",
            )
        if response.status_code >= 400:
            return ComponentHealthView(
                status="down",
                detail=f"OpenAI model check returned HTTP {response.status_code}",
            )
        return ComponentHealthView(
            status="up",
            detail=f"openai:{diagnostic.model}",
        )

    async def open_default_session(self) -> SessionView:
        session_id = await asyncio.to_thread(self._read_selected_session)
        if session_id is not None:
            try:
                return await self.resume(session_id)
            except PersistenceError:
                pass
        return await self.create_session(WorldpackId(self._settings.default_worldpack_id))

    async def _require_session(self, session_id: SessionId) -> _SessionRuntime:
        runtime = self._sessions.get(session_id)
        if runtime is None:
            await self.resume(session_id)
            runtime = self._sessions.get(session_id)
        if runtime is None:
            raise KeyError(session_id)
        return runtime

    async def _compose(
        self,
        *,
        loaded: LoadedWorldpack,
        state_store: JsonFileStateStore,
    ) -> _SessionRuntime:
        state = AuthoritativeStateManager(
            initial_state=loaded.world_state,
            state_store=state_store,
        )
        memory_store = SimpleMemoryAdapter()
        action_port = StructuredLLMPort[
            ActionInterpreterContext, ActionInterpretation
        ](
            task=LLMTask.INTERPRET_ACTION,
            response_model=ActionInterpretation,
            runtime=self._llm_runtime,
        )
        cognition_port = StructuredLLMPort[PrivateCognitiveContext, NPCReactionProposal](
            task=LLMTask.REASON_NPC,
            response_model=NPCReactionProposal,
            runtime=self._llm_runtime,
        )
        focus_port = StructuredLLMPort[
            ConversationFocusContext, ConversationFocusProposal
        ](
            task=LLMTask.INTERPRET_EVENT,
            response_model=ConversationFocusProposal,
            runtime=self._llm_runtime,
        )
        narration_port = StructuredLLMPort[NarrationContext, NarrationProposal](
            task=LLMTask.GENERATE_NARRATION,
            response_model=NarrationProposal,
            runtime=self._llm_runtime,
        )
        audit_port = StructuredLLMPort[NarrationAuditContext, NarrationAuditProposal](
            task=LLMTask.AUDIT_NARRATION,
            response_model=NarrationAuditProposal,
            runtime=self._llm_runtime,
        )
        visual_port = StructuredLLMPort[VisualDirectorContext, RawVST](
            task=LLMTask.GENERATE_VST,
            response_model=RawVST,
            runtime=self._llm_runtime,
        )

        a1111_profile = A1111RenderProfile.from_rendering_config(
            loaded.world_state.rendering_config
        )
        pending_store = JsonPendingRenderStore(self._settings.data_directory / "pending_renders")
        visual_pipeline = VisualTurnPipeline(
            director=VisualDirectorService(port=visual_port),
            canonicalizer=VisualCanonicalizer(),
            compiler=SemanticPromptCompiler(),
            render_request_builder=A1111RenderRequestBuilder(
                settings=self._renderer_settings,
                profile=a1111_profile,
            ),
            renderer=self._renderer,
            diagnostics=AtomicVisualDiagnosticsStore(
                self._settings.data_directory / "visual_diagnostics"
            ),
            pending_renders=pending_store,
        )

        narration = NarrationService(
            port=narration_port,
            audit_port=audit_port,
            validator=NarrationValidator(),
            audit_validator=NarrationAuditValidator(),
        )
        orchestrator = TurnOrchestrator(
            state=state,
            checkpoint=DiceCheckpointService(
                store=JsonFileCheckpointStore(
                    root=self._settings.data_directory / "checkpoints"
                )
            ),
            interpreter=ActionInterpreterService(
                port=action_port,
                validator=ActionValidator(),
            ),
            check_resolver=PythonTurnCheckResolver(
                resolver=CheckResolver(D6OutcomePolicy()),
                rng=random.SystemRandom(),
            ),
            action_resolver=DefaultTurnActionResolver(),
            psychology=PythonTurnPsychologyPlanner(
                psychology=PsychologyService.default(),
                event_source=NoopPsychologicalEventSource(),
                profiles=DefaultPsychologyProfiles(),
                bond_derivation=EmergentBondPolicy(),
            ),
            cognition=NPCCognitionService(
                memory_recall=MemoryRecallService(memory_store),
                port=cognition_port,
                validator=NPCReactionValidator(),
            ),
            reaction_mutations=DefaultReactionMutationPlanner(),
            scene_builder=DefaultTurnSceneBuilder(),
            narration=DefaultTurnNarrationCoordinator(
                focus=ConversationFocusService(
                    port=focus_port,
                    validator=ConversationFocusValidator(),
                ),
                context_builder=NarrationContextBuilder(),
                narration=narration,
            ),
            visual=VisualTurnPipelineAdapter(
                pipeline=visual_pipeline,
                resources=StaticVisualResources(
                    worldpack=loaded,
                    prompt_profile=self._settings.prompt_profile,
                ),
            ),
            memory=TurnMemoryCoordinator(
                derivation=DeterministicTurnMemoryDerivation(),
                capture=MemoryService.default(),
                store=memory_store,
            ),
        )
        return _SessionRuntime(
            loaded_worldpack=loaded,
            state=state,
            orchestrator=orchestrator,
            recovery=RenderRecoveryService(
                store=pending_store,
                executor=A1111PendingRenderExecutor(self._renderer),
            ),
        )

    def _state_store(self) -> JsonFileStateStore:
        return JsonFileStateStore(root=self._settings.data_directory / "states")

    def _worldpack_path(self, worldpack_id: WorldpackId) -> Path:
        root = self._settings.worldpacks_directory.resolve()
        candidate = (root / str(worldpack_id)).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_dir():
            raise ConfigurationError(f"unknown local Worldpack: {worldpack_id}")
        return candidate

    async def _select_session(self, session_id: SessionId) -> None:
        self._current_session_id = session_id
        target = self._settings.data_directory / "current_session.txt"
        await asyncio.to_thread(
            atomic_write_bytes,
            target,
            f"{session_id}\n".encode(),
        )

    def _read_selected_session(self) -> SessionId | None:
        target = self._settings.data_directory / "current_session.txt"
        try:
            raw = target.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise PersistenceError(f"could not read selected session: {exc}") from exc
        return SessionId(raw) if raw else None


def build_local_runtime(
    project_root: Path,
    *,
    environ: dict[str, str] | None = None,
) -> LocalEPOSRuntime:
    settings = load_local_settings(project_root, environ=environ)
    llm_runtime = build_llm_runtime_from_env(settings.environment)
    renderer_settings = A1111AdapterSettings.from_env(
        output_directory=settings.data_directory / "renders",
        environ=settings.environment,
    )
    renderer = A1111ForgeAdapter(
        settings=renderer_settings,
        api=A1111HTTPClient(settings=renderer_settings),
        image_store=AtomicRenderImageStore(renderer_settings.output_directory),
    )
    return LocalEPOSRuntime(
        settings=settings,
        llm_runtime=llm_runtime,
        renderer=renderer,
    )

"""Small deterministic coordinators used by the canonical turn orchestrator."""

from __future__ import annotations

from typing import Generic, TypeVar

from epos.application.actions.checks import CheckResolver
from epos.application.actions.models import CheckProposal, ResolvedCheck, ValidatedAction
from epos.application.cognition.models import CognitionResult
from epos.application.conversation import (
    ConversationFocusContext,
    ConversationFocusService,
    NarrationContextBuilder,
    NarrationResult,
    NarrationService,
)
from epos.application.memory import (
    LongTermMemoryRecord,
    MemoryHit,
    MemoryRecallQuery,
    MemoryService,
)
from epos.application.ports import MemoryStorePort
from epos.application.psychology import PsychologyService
from epos.application.state import (
    MutationAuthority,
    MutationBatch,
    ReplaceNPCBondStateMutation,
    ReplaceNPCEmotionalStateMutation,
    ReplaceNPCMemoryLayersMutation,
    ReplaceNPCRelationshipMutation,
    SetNPCIntentionsMutation,
    SetPlayerLocationMutation,
    StateMutation,
)
from epos.application.turn.errors import TurnOrchestrationError
from epos.application.turn.models import (
    BondDerivationContext,
    CheckDecision,
    TurnActionResolution,
    TurnMemoryContext,
    TurnMemoryPlan,
    TurnPsychologyPlan,
)
from epos.application.turn.ports import (
    BondDerivationPort,
    PsychologyProfilePort,
    TurnMemoryDerivationPort,
    TurnPsychologicalEventPort,
    TurnVisualResourcesPort,
)
from epos.application.visual.bridge import VisualPipelineResult, VisualTurnPipeline
from epos.application.visual.models import ObservableSceneState, SceneObservationInput, SubjectKind
from epos.application.visual.observable_scene import ObservableSceneBuilder
from epos.domain.ids import EntityId
from epos.domain.relationships import RelationshipState
from epos.domain.rng import RandomSource
from epos.domain.world_state import WorldState

RequestT = TypeVar("RequestT")


class PythonTurnCheckResolver:
    """Bind the injected Python RNG to the existing deterministic check resolver."""

    def __init__(self, *, resolver: CheckResolver, rng: RandomSource) -> None:
        self._resolver = resolver
        self._rng = rng

    def resolve(self, proposal: CheckProposal, *, rating: int) -> ResolvedCheck:
        return self._resolver.resolve(proposal, rating=rating, rng=self._rng)


class DefaultTurnActionResolver:
    """Generic baseline for only the authoritative action effects it can prove."""

    def resolve(
        self,
        *,
        state: WorldState,
        action: ValidatedAction,
        check_decision: CheckDecision | None,
        resolved_check: ResolvedCheck | None,
    ) -> TurnActionResolution:
        del state, resolved_check
        if action.outfit_request is not None:
            raise TurnOrchestrationError(
                "default turn resolver has no canonical outfit mutation policy; "
                "inject a Worldpack-specific TurnActionResolverPort",
                code="turn.action.unsupported_outfit_request",
            )
        if action.check is not None and check_decision is CheckDecision.DECLINE:
            return TurnActionResolution()

        mutations: tuple[StateMutation, ...] = ()
        if action.movement is not None:
            mutations = (
                SetPlayerLocationMutation(destination_id=action.movement.destination_id),
            )
        batches = (
            MutationBatch(
                producer=MutationAuthority.ENGINE_ONLY,
                mutations=mutations,
            ),
        ) if mutations else ()
        return TurnActionResolution(mutation_batches=batches)


class PythonTurnPsychologyPlanner:
    """Translate authorized semantic events through Python psychology and bond policies."""

    def __init__(
        self,
        *,
        psychology: PsychologyService,
        event_source: TurnPsychologicalEventPort,
        profiles: PsychologyProfilePort,
        bond_derivation: BondDerivationPort,
    ) -> None:
        self._psychology = psychology
        self._event_source = event_source
        self._profiles = profiles
        self._bond_derivation = bond_derivation

    def plan(
        self,
        *,
        state: WorldState,
        action: ValidatedAction,
        resolved_check: ResolvedCheck | None,
        present_npc_ids: tuple[EntityId, ...],
    ) -> TurnPsychologyPlan:
        events = self._event_source.events_for(
            state=state,
            action=action,
            resolved_check=resolved_check,
            present_npc_ids=present_npc_ids,
        )
        present = set(present_npc_ids)
        for targeted in events:
            if targeted.npc_id not in present:
                raise TurnOrchestrationError(
                    f"psychological event targets off-scene NPC {targeted.npc_id}",
                    code="turn.psychology.offscene_target",
                )

        mutations: list[StateMutation] = []
        player_id = state.player.entity_id
        for npc_id in present_npc_ids:
            npc = state.npcs[npc_id]
            emotions = npc.emotional_state.model_copy(deep=True)
            relationship = npc.relationships.get(player_id, RelationshipState()).model_copy(
                deep=True
            )
            npc_events = tuple(item.event for item in events if item.npc_id == npc_id)
            profile = self._profiles.profile_for(npc_id)
            for event in npc_events:
                update = self._psychology.apply_event(
                    event=event,
                    emotions=emotions,
                    relationship=relationship,
                    profile=profile,
                )
                emotions = update.emotions
                relationship = update.relationship

            if emotions != npc.emotional_state:
                mutations.append(
                    ReplaceNPCEmotionalStateMutation(
                        npc_id=npc_id,
                        emotional_state=emotions,
                    )
                )
            if relationship != npc.relationships.get(player_id, RelationshipState()):
                mutations.append(
                    ReplaceNPCRelationshipMutation(
                        npc_id=npc_id,
                        partner_id=player_id,
                        relationship=relationship,
                    )
                )

            bond = self._bond_derivation.derive(
                BondDerivationContext(
                    npc_id=npc_id,
                    player_id=player_id,
                    current_bond=npc.bond_state.model_copy(deep=True),
                    relationship_with_player=relationship,
                    emotional_state=emotions,
                    core_memory_count=len(npc.core_memories),
                    turn_number=int(state.turn_number),
                    day=state.day,
                    event_types=tuple(event.event_type.value for event in npc_events),
                )
            )
            if bond != npc.bond_state:
                mutations.append(
                    ReplaceNPCBondStateMutation(npc_id=npc_id, bond_state=bond)
                )

        batches = (
            MutationBatch(
                producer=MutationAuthority.ENGINE_ONLY,
                mutations=tuple(mutations),
            ),
        ) if mutations else ()
        return TurnPsychologyPlan(mutation_batches=batches, targeted_events=events)


class DefaultReactionMutationPlanner:
    """Allow validated NPC action intentions to become LLM-proposable state only."""

    def plan(self, reactions: tuple[CognitionResult, ...]) -> MutationBatch:
        mutations = tuple(
            SetNPCIntentionsMutation(
                npc_id=result.reaction.npc_id,
                intentions=(result.reaction.action_intent,),
            )
            for result in reactions
            if result.reaction.action_intent is not None
        )
        return MutationBatch(
            producer=MutationAuthority.LLM_PROPOSABLE,
            mutations=mutations,
        )


class DefaultTurnSceneBuilder:
    def __init__(self, *, builder: ObservableSceneBuilder | None = None) -> None:
        self._builder = builder or ObservableSceneBuilder()

    def build(
        self,
        *,
        state: WorldState,
        action: ValidatedAction,
        resolved_check: ResolvedCheck | None,
        resolution: TurnActionResolution,
    ) -> ObservableSceneState:
        return self._builder.build(
            state=state,
            observation=SceneObservationInput(
                action=action,
                resolved_check=resolved_check,
                subject_cues=resolution.subject_cues,
                observable_consequences=resolution.observable_consequences,
            ),
        )


class DefaultTurnNarrationCoordinator:
    """Connect focus classification and narration to the same canonical scene."""

    def __init__(
        self,
        *,
        focus: ConversationFocusService,
        context_builder: NarrationContextBuilder,
        narration: NarrationService,
    ) -> None:
        self._focus = focus
        self._context_builder = context_builder
        self._narration = narration

    async def generate(
        self,
        *,
        state: WorldState,
        scene: ObservableSceneState,
        player_input: str,
        action: ValidatedAction,
        reactions: tuple[CognitionResult, ...],
    ) -> NarrationResult:
        focus_context = ConversationFocusContext.from_world_state(
            state,
            player_input=player_input,
            action=action,
        )
        focus = await self._focus.classify(focus_context)
        validated_reactions = tuple(result.reaction for result in reactions)
        context = self._context_builder.build(
            state=state,
            scene=scene,
            focus=focus,
            player_input=player_input,
            reactions=validated_reactions,
        )
        return await self._narration.generate(context)


class VisualTurnPipelineAdapter(Generic[RequestT]):
    """Connect Module 18 directly to the complete Module 16 renderer-neutral pipeline."""

    def __init__(
        self,
        *,
        pipeline: VisualTurnPipeline[RequestT],
        resources: TurnVisualResourcesPort,
    ) -> None:
        self._pipeline = pipeline
        self._resources = resources

    async def render(self, scene: ObservableSceneState) -> VisualPipelineResult:
        return await self._pipeline.run(
            scene=scene,
            resources=self._resources.resources_for(scene),
        )


class TurnMemoryCoordinator:
    """Derive once, commit active memory layers, then archive the same validated records."""

    def __init__(
        self,
        *,
        derivation: TurnMemoryDerivationPort,
        capture: MemoryService,
        store: MemoryStorePort[LongTermMemoryRecord, MemoryRecallQuery, MemoryHit],
    ) -> None:
        self._derivation = derivation
        self._capture = capture
        self._store = store

    async def prepare(self, context: TurnMemoryContext) -> TurnMemoryPlan:
        records = await self._derivation.derive(context)
        self._validate_records(context, records)

        mutations: list[StateMutation] = []
        by_npc: dict[EntityId, list[LongTermMemoryRecord]] = {}
        for record in records:
            by_npc.setdefault(record.npc_id, []).append(record)

        for npc_id, npc_records in by_npc.items():
            original = context.state.npcs[npc_id]
            updated = original.model_copy(deep=True)
            existing_ids = {
                memory.memory_id
                for memory in (
                    *original.short_term_memory,
                    *original.core_memories,
                    *original.emotional_memory,
                )
            }
            for record in npc_records:
                if record.memory.memory_id in existing_ids:
                    raise TurnOrchestrationError(
                        f"memory {record.memory.memory_id} already exists for {npc_id}",
                        code="turn.memory.already_exists",
                    )
                existing_ids.add(record.memory.memory_id)
                updated = self._capture.remember(
                    updated,
                    record.memory,
                    perceived=True,
                )

            if (
                updated.short_term_memory != original.short_term_memory
                or updated.core_memories != original.core_memories
                or updated.emotional_memory != original.emotional_memory
            ):
                mutations.append(
                    ReplaceNPCMemoryLayersMutation(
                        npc_id=npc_id,
                        short_term_memory=updated.short_term_memory,
                        core_memories=updated.core_memories,
                        emotional_memory=updated.emotional_memory,
                    )
                )

        batches = (
            MutationBatch(
                producer=MutationAuthority.ENGINE_ONLY,
                mutations=tuple(mutations),
            ),
        ) if mutations else ()
        return TurnMemoryPlan(records=records, mutation_batches=batches)

    async def store(self, plan: TurnMemoryPlan) -> None:
        for record in plan.records:
            await self._store.add(record)

    @staticmethod
    def _validate_records(
        context: TurnMemoryContext,
        records: tuple[LongTermMemoryRecord, ...],
    ) -> None:
        present_npcs = {
            subject.entity_id
            for subject in context.scene.visible_subjects
            if subject.kind is SubjectKind.NPC
        }
        seen: set[tuple[EntityId, str]] = set()
        for record in records:
            if record.npc_id not in present_npcs:
                raise TurnOrchestrationError(
                    f"memory record targets off-scene NPC {record.npc_id}",
                    code="turn.memory.offscene_target",
                )
            if record.npc_id not in context.state.npcs:
                raise TurnOrchestrationError(
                    f"memory record targets unknown NPC {record.npc_id}",
                    code="turn.memory.unknown_npc",
                )
            if record.memory.turn != context.state.turn_number:
                raise TurnOrchestrationError(
                    "memory turn does not match authoritative turn candidate",
                    code="turn.memory.turn_mismatch",
                )
            key = (record.npc_id, str(record.memory.memory_id))
            if key in seen:
                raise TurnOrchestrationError(
                    f"duplicate memory record {record.memory.memory_id} for {record.npc_id}",
                    code="turn.memory.duplicate",
                )
            seen.add(key)

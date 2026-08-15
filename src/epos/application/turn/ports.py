"""Ports that keep the canonical turn orchestrator thin and backend-neutral."""

from __future__ import annotations

from typing import Protocol

from epos.application.actions.models import (
    ActionInterpreterContext,
    CheckProposal,
    ResolvedCheck,
    ValidatedAction,
)
from epos.application.cognition.models import CognitionResult, CognitionScene
from epos.application.conversation.models import NarrationResult
from epos.application.memory import LongTermMemoryRecord
from epos.application.psychology.models import PsychologyProfile
from epos.application.state import MutationBatch
from epos.application.turn.models import (
    BondDerivationContext,
    CheckDecision,
    TargetedPsychologicalEvent,
    TurnActionResolution,
    TurnMemoryContext,
    TurnMemoryPlan,
    TurnPsychologyPlan,
)
from epos.application.visual.bridge import VisualPipelineResources, VisualPipelineResult
from epos.application.visual.models import ObservableSceneState
from epos.domain.bond import BondState
from epos.domain.ids import EntityId
from epos.domain.world_state import WorldState


class TurnActionInterpreterPort(Protocol):
    async def interpret(self, context: ActionInterpreterContext) -> ValidatedAction: ...


class TurnCheckResolverPort(Protocol):
    def resolve(self, proposal: CheckProposal, *, rating: int) -> ResolvedCheck: ...


class TurnActionResolverPort(Protocol):
    def resolve(
        self,
        *,
        state: WorldState,
        action: ValidatedAction,
        check_decision: CheckDecision | None,
        resolved_check: ResolvedCheck | None,
    ) -> TurnActionResolution: ...


class TurnPsychologicalEventPort(Protocol):
    def events_for(
        self,
        *,
        state: WorldState,
        action: ValidatedAction,
        resolved_check: ResolvedCheck | None,
        present_npc_ids: tuple[EntityId, ...],
    ) -> tuple[TargetedPsychologicalEvent, ...]: ...


class PsychologyProfilePort(Protocol):
    def profile_for(self, npc_id: EntityId) -> PsychologyProfile: ...


class BondDerivationPort(Protocol):
    def derive(self, context: BondDerivationContext) -> BondState: ...


class TurnPsychologyPort(Protocol):
    def plan(
        self,
        *,
        state: WorldState,
        action: ValidatedAction,
        resolved_check: ResolvedCheck | None,
        present_npc_ids: tuple[EntityId, ...],
    ) -> TurnPsychologyPlan: ...


class TurnCognitionPort(Protocol):
    async def react(
        self,
        *,
        state: WorldState,
        npc_id: EntityId,
        scene: CognitionScene,
        player_input: str,
        action: ValidatedAction,
        resolved_check: ResolvedCheck | None,
    ) -> CognitionResult | None: ...


class ReactionMutationPlannerPort(Protocol):
    def plan(self, reactions: tuple[CognitionResult, ...]) -> MutationBatch: ...


class TurnScenePort(Protocol):
    def build(
        self,
        *,
        state: WorldState,
        action: ValidatedAction,
        resolved_check: ResolvedCheck | None,
        resolution: TurnActionResolution,
    ) -> ObservableSceneState: ...


class TurnNarrationPort(Protocol):
    async def generate(
        self,
        *,
        state: WorldState,
        scene: ObservableSceneState,
        player_input: str,
        action: ValidatedAction,
        reactions: tuple[CognitionResult, ...],
    ) -> NarrationResult: ...


class TurnVisualResourcesPort(Protocol):
    def resources_for(self, scene: ObservableSceneState) -> VisualPipelineResources: ...


class TurnVisualPort(Protocol):
    async def render(self, scene: ObservableSceneState) -> VisualPipelineResult: ...


class TurnMemoryDerivationPort(Protocol):
    async def derive(
        self,
        context: TurnMemoryContext,
    ) -> tuple[LongTermMemoryRecord, ...]: ...


class TurnMemoryPort(Protocol):
    async def prepare(self, context: TurnMemoryContext) -> TurnMemoryPlan: ...

    async def store(self, plan: TurnMemoryPlan) -> None: ...

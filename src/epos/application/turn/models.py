"""Strict internal contracts used by the canonical turn orchestrator."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from epos.application.actions.models import ResolvedCheck, ValidatedAction
from epos.application.cognition.models import CognitionResult, ValidatedNPCReaction
from epos.application.conversation.models import NarrationResult
from epos.application.intimacy.models import (
    AuthorizedIntimacyVisual,
    IntimacyTurnResolution,
)
from epos.application.memory import LongTermMemoryRecord
from epos.application.psychology.models import PsychologicalEvent
from epos.application.state import (
    MutationAuthority,
    MutationBatch,
    ReplaceNPCMemoryLayersMutation,
)
from epos.application.visual.bridge import VisualPipelineResult
from epos.application.visual.models import (
    ObservableConsequence,
    ObservableSceneState,
    SceneSubjectCue,
)
from epos.domain.base import DomainModel
from epos.domain.bond import BondState
from epos.domain.ids import EntityId, LocationId
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState
from epos.domain.world_state import WorldState


class CheckDecision(StrEnum):
    ROLL = "roll"
    DECLINE = "decline"


class TurnCommand(DomainModel):
    player_input: str
    known_location_ids: tuple[LocationId, ...] = ()
    check_decision: CheckDecision | None = None

    @field_validator("player_input")
    @classmethod
    def validate_player_input(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("player_input must not be empty")
        return normalized


class TurnActionResolution(DomainModel):
    """Python-authorized action effects before NPC psychology/cognition."""

    mutation_batches: tuple[MutationBatch, ...] = ()
    subject_cues: tuple[SceneSubjectCue, ...] = ()
    observable_consequences: tuple[ObservableConsequence, ...] = ()
    authorized_intimacy_visual: AuthorizedIntimacyVisual | None = None


class TargetedPsychologicalEvent(DomainModel):
    npc_id: EntityId
    event: PsychologicalEvent


class BondDerivationContext(DomainModel):
    npc_id: EntityId
    player_id: EntityId
    current_bond: BondState
    relationship_with_player: RelationshipState
    emotional_state: EmotionalState
    core_memory_count: int = Field(ge=0)
    turn_number: int = Field(ge=0)
    day: int = Field(ge=1)
    event_types: tuple[str, ...] = ()


class TurnPsychologyPlan(DomainModel):
    mutation_batches: tuple[MutationBatch, ...] = ()
    targeted_events: tuple[TargetedPsychologicalEvent, ...] = ()


class TurnMemoryDerivationContext(DomainModel):
    """Disclosure-safe material allowed across a memory-classification/LLM boundary."""

    player_input: str
    action: ValidatedAction
    resolved_check: ResolvedCheck | None = None
    reactions: tuple[ValidatedNPCReaction, ...] = ()
    scene: ObservableSceneState
    narration: NarrationResult


class TurnMemoryContext(TurnMemoryDerivationContext):
    """Python-only memory planning context; authoritative state never crosses derivation port."""

    state: WorldState

    def derivation_context(self) -> TurnMemoryDerivationContext:
        return TurnMemoryDerivationContext(
            player_input=self.player_input,
            action=self.action,
            resolved_check=self.resolved_check,
            reactions=self.reactions,
            scene=self.scene,
            narration=self.narration,
        )


class TurnMemoryPlan(DomainModel):
    """One derivation pass: active-layer state effects plus long-term archive records."""

    records: tuple[LongTermMemoryRecord, ...] = ()
    mutation_batches: tuple[MutationBatch, ...] = ()

    @model_validator(mode="after")
    def validate_memory_only_mutations(self) -> Self:
        for batch in self.mutation_batches:
            if batch.producer is not MutationAuthority.ENGINE_ONLY:
                raise ValueError("turn memory mutations must be engine-owned")
            if any(
                not isinstance(mutation, ReplaceNPCMemoryLayersMutation)
                for mutation in batch.mutations
            ):
                raise ValueError("turn memory plan may mutate only NPC memory layers")
        return self


class PostCommitIssue(DomainModel):
    phase: str
    code: str
    message: str
    recovery_action: str = "report_bug"
    retryable: bool = False
    committed_state_preserved: bool = True

    @field_validator("phase", "code", "message", "recovery_action")
    @classmethod
    def validate_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("post-commit issue fields must not be empty")
        return normalized


class TurnOrchestrationResult(DomainModel):
    """Internal technical result. Module 19 owns the public TurnResult contract."""

    committed_state: WorldState
    action: ValidatedAction
    check_decision: CheckDecision | None = None
    resolved_check: ResolvedCheck | None = None
    checkpoint_reused: bool = False
    cognition_results: tuple[CognitionResult, ...] = ()
    intimacy: IntimacyTurnResolution | None = None
    scene: ObservableSceneState
    narration: NarrationResult
    visual: VisualPipelineResult | None = None
    memory_stored: bool = False
    post_commit_issues: tuple[PostCommitIssue, ...] = ()

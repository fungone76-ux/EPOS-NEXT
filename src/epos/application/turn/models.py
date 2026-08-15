"""Strict internal contracts used by the canonical turn orchestrator."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from epos.application.actions.models import ResolvedCheck, ValidatedAction
from epos.application.cognition.models import CognitionResult, ValidatedNPCReaction
from epos.application.conversation.models import NarrationResult
from epos.application.psychology.models import PsychologicalEvent
from epos.application.state import MutationBatch
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


class TurnMemoryContext(DomainModel):
    committed_state: WorldState
    player_input: str
    action: ValidatedAction
    resolved_check: ResolvedCheck | None = None
    reactions: tuple[ValidatedNPCReaction, ...] = ()
    scene: ObservableSceneState
    narration: NarrationResult


class PostCommitIssue(DomainModel):
    phase: str
    code: str
    message: str

    @field_validator("phase", "code", "message")
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
    scene: ObservableSceneState
    narration: NarrationResult
    visual: VisualPipelineResult | None = None
    memory_stored: bool = False
    post_commit_issues: tuple[PostCommitIssue, ...] = ()

"""Small concrete adapters used only by the local composition root."""

from __future__ import annotations

from epos.application.actions import ResolvedCheck, ValidatedAction
from epos.application.memory import LongTermMemoryRecord
from epos.application.psychology import PsychologyProfile
from epos.application.turn import (
    TargetedPsychologicalEvent,
    TurnMemoryDerivationContext,
)
from epos.application.visual.bridge import VisualPipelineResources
from epos.application.visual.models import ObservableSceneState
from epos.application.visual.prompt import PromptCompilerProfile
from epos.application.visual.recovery import PendingRender
from epos.application.visual.rendering import RendererPort, RenderResult
from epos.application.worldpacks import LoadedWorldpack
from epos.domain.ids import EntityId, MemoryId
from epos.domain.memory import MemoryEntryState
from epos.domain.world_state import WorldState
from epos.infrastructure.rendering.a1111 import A1111RenderRequest


class NoopPsychologicalEventSource:
    """Start conservatively until a validated event-classifier adapter is configured."""

    def events_for(
        self,
        *,
        state: WorldState,
        action: ValidatedAction,
        resolved_check: ResolvedCheck | None,
        present_npc_ids: tuple[EntityId, ...],
    ) -> tuple[TargetedPsychologicalEvent, ...]:
        del state, action, resolved_check, present_npc_ids
        return ()


class DefaultPsychologyProfiles:
    def profile_for(self, npc_id: EntityId) -> PsychologyProfile:
        del npc_id
        return PsychologyProfile()


class DeterministicTurnMemoryDerivation:
    """Record the validated public turn once for every NPC that reacted to it."""

    async def derive(
        self,
        context: TurnMemoryDerivationContext,
    ) -> tuple[LongTermMemoryRecord, ...]:
        player_id = next(
            subject.entity_id
            for subject in context.scene.visible_subjects
            if subject.kind.value == "player"
        )
        records: list[LongTermMemoryRecord] = []
        for reaction in context.reactions:
            memory_id = MemoryId(
                f"turn-{int(context.scene.time.turn_number)}-{reaction.npc_id}"
            )
            records.append(
                LongTermMemoryRecord(
                    npc_id=reaction.npc_id,
                    memory=MemoryEntryState(
                        memory_id=memory_id,
                        turn=context.scene.time.turn_number,
                        summary=context.narration.text,
                        participants=(player_id, reaction.npc_id),
                        salience=5.0,
                        tags=reaction.topic_tags,
                    ),
                )
            )
        return tuple(records)


class StaticVisualResources:
    def __init__(
        self,
        *,
        worldpack: LoadedWorldpack,
        prompt_profile: PromptCompilerProfile,
    ) -> None:
        self._worldpack = worldpack.model_copy(deep=True)
        self._prompt_profile = prompt_profile.model_copy(deep=True)

    def resources_for(self, scene: ObservableSceneState) -> VisualPipelineResources:
        return VisualPipelineResources(
            worldpack=self._worldpack,
            prompt_profile=self._prompt_profile,
            seed=int(scene.time.turn_number),
        )


class A1111PendingRenderExecutor:
    def __init__(self, renderer: RendererPort[A1111RenderRequest]) -> None:
        self._renderer = renderer

    async def render(self, pending: PendingRender) -> RenderResult:
        snapshot = pending.render_request
        if snapshot.backend != "a1111":
            return RenderResult(
                status="failed",
                image_path=None,
                backend="a1111",
                prompt_id=snapshot.request_id,
                error=f"pending renderer mismatch: {snapshot.backend}",
                duration_ms=0,
                attempts=1,
            )
        try:
            request = A1111RenderRequest.model_validate(
                {"request_id": snapshot.request_id, **snapshot.payload}
            )
        except ValueError as exc:
            return RenderResult(
                status="failed",
                image_path=None,
                backend="a1111",
                prompt_id=snapshot.request_id,
                error=f"pending A1111 request snapshot is invalid: {exc}",
                duration_ms=0,
                attempts=1,
            )
        return await self._renderer.render(request)

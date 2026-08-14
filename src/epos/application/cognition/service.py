"""Coordinate present-NPC recall, private reasoning, and Python reaction validation."""

from __future__ import annotations

from typing import Protocol

from epos.application.actions.models import ResolvedCheck, ValidatedAction
from epos.application.cognition.context import PrivateCognitiveContextBuilder
from epos.application.cognition.models import (
    CognitionResult,
    CognitionScene,
    NPCReactionProposal,
    PrivateCognitiveContext,
)
from epos.application.cognition.validation import NPCReactionValidator
from epos.application.memory import MemoryRecallQuery, MemoryRecallResult
from epos.application.ports import LLMPort
from epos.domain.errors import EposValidationError
from epos.domain.ids import EntityId, MemoryId
from epos.domain.world_state import WorldState


class CognitionServiceError(EposValidationError):
    def __init__(self, message: str, *, code: str = "cognition.service.failed") -> None:
        super().__init__(message, code=code)


class MemoryRecallProtocol(Protocol):
    async def recall(
        self,
        query: MemoryRecallQuery,
        *,
        limit: int = 6,
    ) -> MemoryRecallResult: ...


class NPCCognitionService:
    def __init__(
        self,
        *,
        memory_recall: MemoryRecallProtocol,
        port: LLMPort[PrivateCognitiveContext, NPCReactionProposal],
        validator: NPCReactionValidator,
        context_builder: PrivateCognitiveContextBuilder | None = None,
        recall_limit: int = 6,
    ) -> None:
        if recall_limit < 1 or recall_limit > 12:
            raise ValueError("recall_limit must be between 1 and 12")
        self._memory_recall = memory_recall
        self._port = port
        self._validator = validator
        self._context_builder = context_builder or PrivateCognitiveContextBuilder()
        self._recall_limit = recall_limit

    async def react(
        self,
        *,
        state: WorldState,
        npc_id: EntityId,
        scene: CognitionScene,
        player_input: str,
        action: ValidatedAction,
        resolved_check: ResolvedCheck | None,
    ) -> CognitionResult | None:
        npc = state.npcs.get(npc_id)
        if npc is None:
            raise CognitionServiceError(f"unknown NPC: {npc_id}")

        if npc.location_id != state.player.location_id:
            return None

        recall = await self._memory_recall.recall(
            MemoryRecallQuery(
                npc_id=npc_id,
                player_input=player_input,
                scene_context=self._scene_query_text(scene),
                current_goals=npc.goals,
                current_turn=state.turn_number,
            ),
            limit=self._recall_limit,
        )
        context = self._context_builder.build(
            state=state,
            npc_id=npc_id,
            scene=scene,
            player_input=player_input,
            action=action,
            recalled=recall,
            resolved_check=resolved_check,
        )
        proposal = await self._port.invoke(context)
        reaction = self._validator.validate(proposal, context)
        memory_ids: tuple[MemoryId, ...] = tuple(
            ranked.memory.memory_id for ranked in recall.memories
        )
        return CognitionResult(reaction=reaction, recalled_memory_ids=memory_ids)

    @staticmethod
    def _scene_query_text(scene: CognitionScene) -> str:
        parts = (scene.summary, *scene.observable_facts)
        return " ".join(part.strip() for part in parts if part.strip())

from __future__ import annotations

from epos.application.actions.models import ValidatedAction
from epos.application.cognition.models import CognitionScene, NPCReactionProposal, PrivateCognitiveContext
from epos.application.cognition.service import NPCCognitionService
from epos.application.cognition.validation import NPCReactionValidator
from epos.application.memory import MemoryRecallQuery, MemoryRecallResult, RankedMemory
from epos.domain.ids import EntityId, LocationId, MemoryId, SessionId, TurnNumber, WorldpackId
from epos.domain.memory import MemoryEntryState
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, WorldState


class PromiseRecall:
    async def recall(self, query: MemoryRecallQuery, *, limit: int = 6) -> MemoryRecallResult:
        del query, limit
        memory = MemoryEntryState(
            memory_id=MemoryId("old_promise"),
            turn=TurnNumber(2),
            summary="The player promised Victoria they would come back for the key.",
            participants=(EntityId("player"), EntityId("victoria")),
            salience=9.0,
            tags=("promise",),
        )
        return MemoryRecallResult(
            query_text="key promise",
            memories=(RankedMemory(memory=memory, semantic_score=0.93, relevance_score=0.97),),
        )


class MemoryAwareCognitionPort:
    def __init__(self) -> None:
        self.seen_memory_ids: tuple[MemoryId, ...] = ()

    async def invoke(self, request: PrivateCognitiveContext) -> NPCReactionProposal:
        self.seen_memory_ids = tuple(item.memory.memory_id for item in request.recalled_memories)
        return NPCReactionProposal(
            npc_id=request.npc_id,
            intent="acknowledge_old_promise",
            communication_goal="answer while accounting for the old promise",
            referenced_memory_ids=self.seen_memory_ids,
            target_ids=(request.player_id,),
        )


async def test_recalled_memory_is_consumed_by_npc_reasoning_context() -> None:
    lobby = LocationId("lobby")
    player_id = EntityId("player")
    victoria_id = EntityId("victoria")
    state = WorldState(
        session_id=SessionId("s"),
        worldpack_id=WorldpackId("resort_world"),
        turn_number=TurnNumber(100),
        day=7,
        world_phase="evening",
        player=PlayerState(entity_id=player_id, name="Alex", location_id=lobby),
        npcs={
            victoria_id: NPCState(
                identity=NPCIdentity(entity_id=victoria_id, name="Victoria", role="host"),
                location_id=lobby,
                goals=("recover the key",),
            )
        },
        locations={lobby: LocationState(location_id=lobby, name="Lobby")},
    )
    port = MemoryAwareCognitionPort()
    service = NPCCognitionService(
        memory_recall=PromiseRecall(),
        port=port,
        validator=NPCReactionValidator(),
    )

    result = await service.react(
        state=state,
        npc_id=victoria_id,
        scene=CognitionScene(
            location_id=lobby,
            present_entity_ids=(player_id, victoria_id),
            summary="The player meets Victoria in the lobby.",
        ),
        player_input="Ti ricordi della chiave?",
        action=ValidatedAction(intent="dialogue", target_ids=(victoria_id,)),
        resolved_check=None,
    )

    assert result is not None
    assert port.seen_memory_ids == (MemoryId("old_promise"),)
    assert result.reaction.intent == "acknowledge_old_promise"
    assert result.reaction.referenced_memory_ids == (MemoryId("old_promise"),)

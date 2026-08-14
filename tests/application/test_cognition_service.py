from __future__ import annotations

from epos.application.actions.models import ValidatedAction
from epos.application.cognition.models import CognitionScene, NPCReactionProposal
from epos.application.cognition.service import NPCCognitionService
from epos.application.cognition.validation import NPCReactionValidator
from epos.application.memory import MemoryRecallQuery, MemoryRecallResult
from epos.domain.ids import EntityId, LocationId, SessionId, TurnNumber, WorldpackId
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.player import PlayerState
from epos.domain.world_state import LocationState, WorldState


class FakeRecall:
    def __init__(self) -> None:
        self.calls = 0

    async def recall(self, query: MemoryRecallQuery, *, limit: int = 6) -> MemoryRecallResult:
        del query, limit
        self.calls += 1
        return MemoryRecallResult(query_text="", memories=())


class FakeCognitionPort:
    def __init__(self) -> None:
        self.calls = 0

    async def invoke(self, request: object) -> NPCReactionProposal:
        del request
        self.calls += 1
        return NPCReactionProposal(
            npc_id=EntityId("victoria"),
            intent="respond",
            speech_act="acknowledge",
            topic_tags=("local_exchange",),
            target_ids=(EntityId("player"),),
        )


def _state(*, npc_location: str) -> WorldState:
    lobby = LocationId("lobby")
    npc_location_id = LocationId(npc_location)
    victoria_id = EntityId("victoria")
    return WorldState(
        session_id=SessionId("s"),
        worldpack_id=WorldpackId("resort_world"),
        turn_number=TurnNumber(4),
        day=1,
        world_phase="morning",
        player=PlayerState(entity_id=EntityId("player"), name="Alex", location_id=lobby),
        npcs={
            victoria_id: NPCState(
                identity=NPCIdentity(entity_id=victoria_id, name="Victoria", role="host"),
                location_id=npc_location_id,
            )
        },
        locations={
            lobby: LocationState(location_id=lobby, name="Lobby"),
            npc_location_id: LocationState(location_id=npc_location_id, name=npc_location),
        },
    )


async def test_offscreen_npc_does_not_recall_or_call_llm() -> None:
    recall = FakeRecall()
    port = FakeCognitionPort()
    service = NPCCognitionService(memory_recall=recall, port=port, validator=NPCReactionValidator())

    result = await service.react(
        state=_state(npc_location="pool"),
        npc_id=EntityId("victoria"),
        scene=CognitionScene(
            location_id=LocationId("lobby"),
            present_entity_ids=(EntityId("player"),),
            summary="Lobby.",
        ),
        player_input="Victoria?",
        action=ValidatedAction(intent="dialogue"),
        resolved_check=None,
    )

    assert result is None
    assert recall.calls == 0
    assert port.calls == 0


async def test_present_npc_runs_recall_then_cognition() -> None:
    recall = FakeRecall()
    port = FakeCognitionPort()
    service = NPCCognitionService(memory_recall=recall, port=port, validator=NPCReactionValidator())

    result = await service.react(
        state=_state(npc_location="lobby"),
        npc_id=EntityId("victoria"),
        scene=CognitionScene(
            location_id=LocationId("lobby"),
            present_entity_ids=(EntityId("player"), EntityId("victoria")),
            summary="Lobby.",
        ),
        player_input="Buona sera Victoria.",
        action=ValidatedAction(intent="dialogue", target_ids=(EntityId("victoria"),)),
        resolved_check=None,
    )

    assert result is not None
    assert result.reaction.npc_id == EntityId("victoria")
    assert result.reaction.speech_act == "acknowledge"
    assert recall.calls == 1
    assert port.calls == 1

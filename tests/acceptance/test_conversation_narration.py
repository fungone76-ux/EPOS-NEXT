from __future__ import annotations

import pytest

from epos.application.actions.models import ValidatedAction
from epos.application.cognition.models import CognitionScene, ValidatedNPCReaction
from epos.application.conversation.context import NarrationContextBuilder
from epos.application.conversation.focus import ConversationFocusService, ConversationFocusValidator
from epos.application.conversation.models import (
    ConversationFocusContext,
    ConversationFocusProposal,
    NarrationContext,
    NarrationMode,
    NarrationProposal,
    NPCDialogueDraft,
)
from epos.application.conversation.narration import NarrationService
from epos.application.conversation.validation import NarrationValidator
from epos.domain.ids import EntityId, LocationId, SessionId, TurnNumber, WorldpackId
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.player import PlayerState
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState
from epos.domain.world_state import LocationState, WorldState


class GreetingFocusPort:
    async def invoke(self, request: ConversationFocusContext) -> ConversationFocusProposal:
        assert request.player_input == "Buona sera Victoria!"
        return ConversationFocusProposal(
            speaker_id=request.player_id,
            target_npc_id=EntityId("victoria"),
            topic="greeting",
            mode=NarrationMode.BRIEF_SOCIAL,
        )


class EmotionAwareNarratorPort:
    async def invoke(self, request: NarrationContext) -> NarrationProposal:
        victoria = next(voice for voice in request.voices if voice.npc_id == EntityId("victoria"))
        text = "Buona sera." if victoria.emotional_state.anger >= 8 else "Buona sera, che piacere."
        return NarrationProposal(
            units=(
                NPCDialogueDraft(
                    speaker_id=EntityId("victoria"),
                    text=text,
                    evidence_ids=("reaction:victoria",),
                ),
            )
        )


def _state(*, anger: float, trust: float) -> WorldState:
    player_id = EntityId("player")
    victoria_id = EntityId("victoria")
    stella_id = EntityId("stella")
    lobby = LocationId("lobby")
    return WorldState(
        session_id=SessionId("session"),
        worldpack_id=WorldpackId("resort_world"),
        turn_number=TurnNumber(12),
        day=2,
        world_phase="evening",
        player=PlayerState(entity_id=player_id, name="Alex", location_id=lobby),
        npcs={
            victoria_id: NPCState(
                identity=NPCIdentity(entity_id=victoria_id, name="Victoria", role="host"),
                location_id=lobby,
                personality=("controlled", "elegant"),
                speech_style="precise",
                emotional_state=EmotionalState(anger=anger),
                relationships={player_id: RelationshipState(trust=trust)},
            ),
            stella_id: NPCState(
                identity=NPCIdentity(entity_id=stella_id, name="Stella", role="guest"),
                location_id=lobby,
            ),
        },
        locations={lobby: LocationState(location_id=lobby, name="Lobby")},
    )


async def _run(*, anger: float, trust: float) -> str:
    state = _state(anger=anger, trust=trust)
    action = ValidatedAction(intent="dialogue", target_ids=(EntityId("victoria"),))
    focus_context = ConversationFocusContext.from_world_state(
        state,
        player_input="Buona sera Victoria!",
        action=action,
    )
    focus = await ConversationFocusService(
        port=GreetingFocusPort(),
        validator=ConversationFocusValidator(),
    ).classify(focus_context)
    reaction = ValidatedNPCReaction(
        npc_id=EntityId("victoria"),
        intent="respond_to_greeting",
        speech_act="acknowledge",
        topic_tags=("greeting",),
        emotional_tone=("controlled",),
        target_ids=(EntityId("player"),),
    )
    narration_context = NarrationContextBuilder().build(
        state=state,
        scene=CognitionScene(
            location_id=LocationId("lobby"),
            present_entity_ids=(EntityId("player"), EntityId("victoria"), EntityId("stella")),
            summary="Il player saluta Victoria nella hall.",
        ),
        focus=focus,
        player_input="Buona sera Victoria!",
        action=action,
        resolved_check=None,
        reactions=(reaction,),
    )
    result = await NarrationService(
        port=EmotionAwareNarratorPort(),
        validator=NarrationValidator(),
    ).generate(narration_context)
    return result.text


@pytest.mark.asyncio
async def test_greeting_stays_brief_focused_and_preserves_player_agency() -> None:
    text = await _run(anger=1.0, trust=8.0)

    assert text == "Victoria: Buona sera, che piacere."
    assert "Stella:" not in text
    assert "Alex:" not in text


@pytest.mark.asyncio
async def test_same_greeting_changes_when_victoria_emotional_state_changes() -> None:
    warm = await _run(anger=1.0, trust=8.0)
    angry = await _run(anger=9.0, trust=2.0)

    assert warm != angry
    assert angry == "Victoria: Buona sera."

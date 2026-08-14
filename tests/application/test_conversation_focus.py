from __future__ import annotations

import pytest

from epos.application.actions.models import ValidatedAction
from epos.application.conversation.focus import ConversationFocusService, ConversationFocusValidator
from epos.application.conversation.models import (
    ConversationFocusContext,
    ConversationFocusProposal,
    NarrationMode,
)
from epos.application.conversation.validation import ConversationFocusValidationError
from epos.domain.ids import EntityId, LocationId


class FakeFocusPort:
    def __init__(self, proposal: ConversationFocusProposal) -> None:
        self.proposal = proposal
        self.inputs: list[str] = []

    async def invoke(self, request: ConversationFocusContext) -> ConversationFocusProposal:
        self.inputs.append(request.player_input)
        return self.proposal


def _context(player_input: str = "Buona sera Victoria!") -> ConversationFocusContext:
    return ConversationFocusContext(
        player_id=EntityId("player"),
        player_input=player_input,
        location_id=LocationId("lobby"),
        present_npc_ids=(EntityId("victoria"), EntityId("stella")),
        npc_names={
            EntityId("victoria"): "Victoria",
            EntityId("stella"): "Stella",
        },
        action=ValidatedAction(
            intent="dialogue",
            target_ids=(EntityId("victoria"),),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "greeting",
    ("buonasera", "buona sera", "salve Victoria", "ciao Victoria", "ehi Victoria!"),
)
async def test_focus_service_delegates_semantic_classification_with_exact_input(
    greeting: str,
) -> None:
    proposal = ConversationFocusProposal(
        speaker_id=EntityId("player"),
        target_npc_id=EntityId("victoria"),
        topic="greeting",
        mode=NarrationMode.BRIEF_SOCIAL,
    )
    port = FakeFocusPort(proposal)
    service = ConversationFocusService(port=port, validator=ConversationFocusValidator())

    focus = await service.classify(_context(greeting))

    assert port.inputs == [greeting]
    assert focus.mode is NarrationMode.BRIEF_SOCIAL
    assert focus.target_npc_id == EntityId("victoria")


def test_focus_validator_rejects_non_player_speaker() -> None:
    proposal = ConversationFocusProposal(
        speaker_id=EntityId("victoria"),
        target_npc_id=EntityId("victoria"),
        topic="greeting",
        mode=NarrationMode.BRIEF_SOCIAL,
    )

    with pytest.raises(ConversationFocusValidationError, match="speaker"):
        ConversationFocusValidator().validate(proposal, _context())


def test_focus_validator_rejects_unrelated_target_when_player_addressed_victoria() -> None:
    proposal = ConversationFocusProposal(
        speaker_id=EntityId("player"),
        target_npc_id=EntityId("stella"),
        topic="greeting",
        mode=NarrationMode.BRIEF_SOCIAL,
    )

    with pytest.raises(ConversationFocusValidationError, match="target"):
        ConversationFocusValidator().validate(proposal, _context())


def test_focus_validator_rejects_off_scene_target() -> None:
    proposal = ConversationFocusProposal(
        speaker_id=EntityId("player"),
        target_npc_id=EntityId("luna"),
        topic="question",
        mode=NarrationMode.DIRECT_DIALOGUE,
    )

    with pytest.raises(ConversationFocusValidationError, match="present"):
        ConversationFocusValidator().validate(proposal, _context())

from epos.application.conversation.models import (
    ConversationFocus,
    NarrationMode,
    NarrationResult,
    NPCDialogueDraft,
    WorldNarrationDraft,
)
from epos.application.results.mapper import TurnResultMapper
from epos.domain.ids import EntityId


def _focus() -> ConversationFocus:
    return ConversationFocus(
        speaker_id=EntityId("player"),
        target_npc_id=EntityId("victoria"),
        topic="greeting",
        mode=NarrationMode.BRIEF_SOCIAL,
    )


def test_dialogue_only_turn_has_no_duplicate_world_narration_text() -> None:
    narration = NarrationResult(
        focus=_focus(),
        units=(
            NPCDialogueDraft(
                speaker_id=EntityId("victoria"),
                text="Buongiorno. È un piacere vederti qui.",
            ),
        ),
        text="Victoria Hale: Buongiorno. È un piacere vederti qui.",
    )

    assert TurnResultMapper._world_narration(narration) == ""


def test_world_narration_and_dialogue_are_separated_for_presentation() -> None:
    narration = NarrationResult(
        focus=_focus(),
        units=(
            WorldNarrationDraft(
                text="La luce del mattino attraversa la lobby.",
            ),
            NPCDialogueDraft(
                speaker_id=EntityId("victoria"),
                text="Buongiorno.",
            ),
        ),
        text="La luce del mattino attraversa la lobby.\nVictoria Hale: Buongiorno.",
    )

    assert (
        TurnResultMapper._world_narration(narration)
        == "La luce del mattino attraversa la lobby."
    )

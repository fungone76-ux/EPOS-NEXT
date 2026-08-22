from epos.application.conversation.context import NarrationContextBuilder
from epos.domain.character_definition import NPCCharacterDefinition
from epos.domain.ids import EntityId, LocationId
from epos.domain.npc import NPCIdentity, NPCState


def test_narration_voice_prefers_character_definition_over_legacy_fields() -> None:
    npc = NPCState(
        identity=NPCIdentity(
            entity_id=EntityId("victoria"),
            name="Victoria",
            role="host",
        ),
        location_id=LocationId("lobby"),
        character_definition=NPCCharacterDefinition(
            personality=("controlled", "strategic"),
            speech_style="Concise and dry.",
        ),
        personality=("legacy_personality",),
        speech_style="Legacy style.",
    )

    voice = NarrationContextBuilder._voice(npc, EntityId("player"))

    assert voice.personality == ("controlled", "strategic")
    assert voice.speech_style == "Concise and dry."


def test_narration_voice_falls_back_to_legacy_fields_for_old_worldpacks() -> None:
    npc = NPCState(
        identity=NPCIdentity(
            entity_id=EntityId("legacy_npc"),
            name="Legacy",
            role="guest",
        ),
        location_id=LocationId("lobby"),
        personality=("reserved",),
        speech_style="Formal.",
    )

    voice = NarrationContextBuilder._voice(npc, EntityId("player"))

    assert voice.personality == ("reserved",)
    assert voice.speech_style == "Formal."

from epos.application.worldpacks.assembler import WorldpackAssembler
from epos.application.worldpacks.models import (
    LocationsDocument,
    NPCDefinition,
    NPCsDocument,
    SkillsDocument,
    WorldDocument,
    WorldpackBundle,
    WorldpackPlayerDefinition,
)
from epos.domain.character_definition import ExampleDialogue, NPCCharacterDefinition
from epos.domain.ids import EntityId, LocationId, WorldpackId
from epos.domain.world_state import LocationState


def test_worldpack_character_definition_reaches_runtime_npc_state() -> None:
    lobby = LocationId("lobby")
    victoria_id = EntityId("victoria")
    definition = NPCCharacterDefinition(
        short_description="Controlled resort host.",
        speech_style="Elegant, concise, dryly ironic.",
        values=("loyalty", "self-control"),
        example_dialogues=(
            ExampleDialogue(
                player="Sei arrabbiata?",
                npc="No. Ma continua a chiederlo e potrei cambiare idea.",
            ),
        ),
    )
    bundle = WorldpackBundle(
        world=WorldDocument(
            worldpack_id=WorldpackId("resort_world"),
            title="Resort",
            initial_phase="evening",
            player=WorldpackPlayerDefinition(
                entity_id=EntityId("player"),
                name="Alex",
                location_id=lobby,
            ),
        ),
        locations=LocationsDocument(
            locations=(LocationState(location_id=lobby, name="Lobby"),),
        ),
        npcs=NPCsDocument(
            npcs=(
                NPCDefinition(
                    entity_id=victoria_id,
                    name="Victoria",
                    role="host",
                    location_id=lobby,
                    character_definition=definition,
                ),
            ),
        ),
        skills=SkillsDocument(),
    )

    loaded = WorldpackAssembler().build(bundle, session_id="session")

    runtime = loaded.world_state.npcs[victoria_id]
    assert runtime.character_definition == definition
    assert runtime.character_definition.example_dialogues[0].player == "Sei arrabbiata?"
    assert runtime.character_definition.values == ("loyalty", "self-control")

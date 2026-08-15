from pathlib import Path

from epos.domain.ids import EntityId, SkillId, WorldpackId
from epos.infrastructure.worldpacks.loader import FileSystemWorldpackLoader


async def test_reference_worldpacks_load_without_core_changes() -> None:
    loader = FileSystemWorldpackLoader()

    resort = await loader.load(Path("worldpacks/resort_world"), session_id="acceptance-resort")
    test_world = await loader.load(Path("worldpacks/test_world"), session_id="acceptance-test")

    assert resort.world_state.worldpack_id == WorldpackId("resort_world")
    assert test_world.world_state.worldpack_id == WorldpackId("test_world")
    assert set(resort.world_state.npcs) == {
        EntityId("victoria"),
        EntityId("stella"),
        EntityId("maria"),
        EntityId("luna"),
    }
    assert set(test_world.world_state.npcs) == {EntityId("theron")}
    assert set(resort.world_state.skill_definitions) == {
        SkillId("autorita"),
        SkillId("carisma"),
        SkillId("intuito"),
        SkillId("negoziazione"),
        SkillId("prestanza"),
    }
    assert set(test_world.world_state.skill_definitions) == {SkillId("sarissa")}
    assert resort.world_state.model_dump() != test_world.world_state.model_dump()

from __future__ import annotations

from pathlib import Path

import yaml

from epos.domain.ids import EntityId
from epos.infrastructure.worldpacks import FileSystemWorldpackLoader

ROOT = Path("worldpacks/resort_world")
SOURCE = ROOT / "source"


def _yaml(name: str) -> dict[str, object]:
    raw = yaml.safe_load((SOURCE / name).read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


async def test_converted_resort_preserves_authored_campaign_and_character_content() -> None:
    authored_world = _yaml("world.yaml")
    authored_npcs = _yaml("npcs.yaml")
    loaded = await FileSystemWorldpackLoader().load(ROOT, session_id="source-fidelity")
    state = loaded.world_state

    assert state.worldpack_id == authored_world["world_id"]
    assert state.world_phase == authored_world["start_time_phase"]
    assert state.player.location_id == authored_world["start_location_id"]
    assert state.narrative_config.settings["premise"] == authored_world["premise"]
    assert (
        state.narrative_config.settings["opening_narration"]
        == authored_world["opening_narration"]
    )

    npc_documents = authored_npcs["npcs"]
    assert isinstance(npc_documents, list)
    for authored in npc_documents:
        assert isinstance(authored, dict)
        npc = state.npcs[EntityId(authored["id"])]
        assert npc.identity.name == authored["name"]
        assert list(npc.personality) == authored["personality"]
        assert list(npc.desires) == authored["desires"]
        assert list(npc.fears) == authored["fears"]
        assert list(npc.goals) == authored["goals"]
        assert npc.stats == authored["skills"]
        assert [item.name for item in npc.outfit.items] == authored["starting_outfit"]


async def test_converted_resort_preserves_every_authored_outfit_and_visual_prompt() -> None:
    authored_wardrobes = _yaml("wardrobes.yaml")["wardrobes"]
    authored_visuals = _yaml("visual.yaml")
    loaded = await FileSystemWorldpackLoader().load(ROOT, session_id="visual-fidelity")

    assert isinstance(authored_wardrobes, dict)
    for owner_id, days in authored_wardrobes.items():
        assert isinstance(days, dict)
        for day, phases in days.items():
            assert isinstance(phases, dict)
            for phase, authored_items in phases.items():
                outfit_id = f"{owner_id}_day_{day}_{phase}"
                converted = loaded.world_state.wardrobes[outfit_id]
                assert [item.name for item in converted.items] == authored_items

    characters = authored_visuals["characters"]
    assert isinstance(characters, list)
    for authored in characters:
        assert isinstance(authored, dict)
        converted = loaded.visual.characters[EntityId(authored["id"])]
        assert converted.base_prompt == authored["base_prompt"]
        assert converted.role_prompt == authored["role_prompt_en"]


async def test_converted_resort_keeps_all_missions_events_and_schedule_entries() -> None:
    authored_world = _yaml("world.yaml")
    authored_events = _yaml("events.yaml")["events"]
    authored_schedules = _yaml("schedules.yaml")["schedules"]
    loaded = await FileSystemWorldpackLoader().load(ROOT, session_id="structure-fidelity")

    assert set(loaded.world_state.missions) == {
        mission["id"] for mission in authored_world["missions"]
    }
    assert set(loaded.world_state.events) == {event["id"] for event in authored_events}
    assert isinstance(authored_schedules, dict)
    for schedule in loaded.schedules.schedules:
        expected = sum(len(phases) for phases in authored_schedules[str(schedule.npc_id)].values())
        assert len(schedule.entries) == expected


async def test_adult_library_preserves_all_authored_entries_and_prompt_fragments() -> None:
    authored = _yaml("sex_library.yaml")
    loaded = await FileSystemWorldpackLoader().load(ROOT, session_id="adult-fidelity")

    assert loaded.sex_library is not None
    authored_entries = authored["entries"]
    assert isinstance(authored_entries, list)
    assert len(loaded.sex_library.entries) == len(authored_entries) == 151
    assert {
        entry.entry_id: entry.positive_fragment for entry in loaded.sex_library.entries
    } == {
        entry["entry_id"]: entry["positive_fragment"] for entry in authored_entries
    }

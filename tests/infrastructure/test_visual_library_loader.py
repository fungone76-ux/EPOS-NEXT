from __future__ import annotations

from pathlib import Path

import pytest

from epos.infrastructure.worldpacks.loader import FileSystemWorldpackLoader


@pytest.mark.asyncio
async def test_filesystem_loader_reads_all_seven_visual_semantic_libraries(
    tmp_path: Path,
) -> None:
    (tmp_path / "world.yaml").write_text(
        """
worldpack_id: visual-test
 title: Visual Test
initial_phase: day
player:
  entity_id: player
  name: Player
  location_id: room
""".replace(" title:", "title:"),
        encoding="utf-8",
    )
    (tmp_path / "locations.yaml").write_text(
        """
locations:
  - location_id: room
    name: Room
""",
        encoding="utf-8",
    )
    (tmp_path / "npcs.yaml").write_text("npcs: []\n", encoding="utf-8")
    (tmp_path / "skills.yaml").write_text("skills: []\n", encoding="utf-8")

    filenames = (
        "action_library.yaml",
        "pose_library.yaml",
        "camera_library.yaml",
        "outfit_library.yaml",
        "lighting_library.yaml",
        "location_visual_library.yaml",
        "style_library.yaml",
    )
    for index, filename in enumerate(filenames):
        (tmp_path / filename).write_text(
            f"""
entries:
  - entry_id: entry_{index}
    description: semantic entry {index}
    aliases:
      - alias {index}
    tags:
      - tag_{index}
    positive_fragment: prompt fragment {index}
""",
            encoding="utf-8",
        )

    loaded = await FileSystemWorldpackLoader().load(tmp_path, session_id="session-loader")

    libraries = (
        loaded.action_library,
        loaded.pose_library,
        loaded.camera_library,
        loaded.outfit_library,
        loaded.lighting_library,
        loaded.location_visual_library,
        loaded.style_library,
    )
    assert tuple(library.entries[0].entry_id for library in libraries) == tuple(
        f"entry_{index}" for index in range(7)
    )
    assert tuple(library.entries[0].positive_fragment for library in libraries) == tuple(
        f"prompt fragment {index}" for index in range(7)
    )

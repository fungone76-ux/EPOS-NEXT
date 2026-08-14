from __future__ import annotations

from epos.application.visual.canonical import SemanticLibraryResolver
from epos.application.visual.vst import SemanticIntent
from epos.application.worldpacks.models import (
    LoadedWorldpack,
    SemanticLibraryDocument,
    SemanticLibraryEntry,
    WorldpackBundle,
)


def test_semantic_library_entry_accepts_aliases_and_positive_fragment() -> None:
    entry = SemanticLibraryEntry(
        entry_id="pool_edge_lean",
        description="standing while leaning lightly against the pool edge",
        aliases=("leaning by the pool", "casually leaning near the pool"),
        tags=("standing", "leaning", "pool"),
        positive_fragment="standing, leaning lightly against the pool edge",
    )

    assert entry.aliases == ("leaning by the pool", "casually leaning near the pool")
    assert entry.positive_fragment == "standing, leaning lightly against the pool edge"


def test_semantic_resolver_matches_authored_alias_and_carries_positive_fragment() -> None:
    library = SemanticLibraryDocument(
        entries=(
            SemanticLibraryEntry(
                entry_id="pool_edge_lean",
                description="standing while leaning lightly against the pool edge",
                aliases=("casually leaning near the pool",),
                tags=("standing", "leaning", "pool"),
                positive_fragment="standing, leaning lightly against the pool edge",
            ),
        )
    )

    resolved = SemanticLibraryResolver().resolve(
        SemanticIntent(description="Casually leaning near the pool"),
        library,
        library_name="pose",
    )

    assert resolved.entry_id == "pool_edge_lean"
    assert resolved.positive_fragment == "standing, leaning lightly against the pool edge"


def test_worldpack_contract_exposes_all_seven_visual_libraries() -> None:
    expected = {
        "action_library",
        "pose_library",
        "camera_library",
        "outfit_library",
        "lighting_library",
        "location_visual_library",
        "style_library",
    }

    assert expected <= set(WorldpackBundle.model_fields)
    assert expected <= set(LoadedWorldpack.model_fields)

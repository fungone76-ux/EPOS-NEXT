from __future__ import annotations

import gzip
import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from epos.application.visual.canonical import (
    CanonicalAction,
    CanonicalCamera,
    CanonicalLocation,
    CanonicalSubject,
    CanonicalVisualFocus,
    CanonicalVisualIdentity,
    CanonicalVST,
    ResolvedSemanticEntry,
    SemanticLibraryResolutionError,
)
from epos.application.visual.models import SceneTime, SubjectKind
from epos.application.visual.prompt import (
    PromptCompilerProfile,
    SemanticPromptCompiler,
    WorldpackVisualConfig,
)
from epos.application.visual.vst import (
    SemanticIntent,
    VSTLightingIntent,
    VSTSafetyIntent,
    VSTStyleIntent,
    VSTSubjectProminence,
)
from epos.application.worldpacks.assembler import WorldpackValidationError
from epos.application.worldpacks.models import (
    AdultSemanticLibraryDocument,
    SemanticLibraryDocument,
    SemanticLibraryEntry,
)
from epos.domain.ids import EntityId, LocationId, SceneId, WorldpackId
from epos.domain.outfit import OutfitItem, OutfitState
from epos.domain.visual_state import VisualState
from epos.infrastructure.worldpacks.loader import FileSystemWorldpackLoader

RESORT_ROOT = Path("worldpacks/resort_world")


def _entry(entry_id: str, *, aliases: tuple[str, ...] = ()) -> SemanticLibraryEntry:
    return SemanticLibraryEntry(
        entry_id=entry_id,
        description=entry_id.replace("_", " "),
        aliases=aliases,
        tags=("test",),
        positive_fragment=f"render {entry_id}",
    )


def test_semantic_library_metadata_is_strict_and_versioned() -> None:
    document = SemanticLibraryDocument(
        schema_version=1,
        library_id="action_library",
        description="Action library",
        world_id=WorldpackId("resort_world"),
        entries=(_entry("walking"),),
    )

    assert document.schema_version == 1
    assert document.library_id == "action_library"
    assert document.world_id == WorldpackId("resort_world")

    with pytest.raises(ValidationError, match="schema_version"):
        SemanticLibraryDocument.model_validate(
            {
                "schema_version": 2,
                "library_id": "action_library",
                "entries": [],
            }
        )


def test_cross_entry_exact_alias_collision_is_rejected() -> None:
    with pytest.raises(ValidationError, match="alias"):
        SemanticLibraryDocument(
            entries=(
                _entry("standing_hand_hip", aliases=("hand on hip",)),
                _entry("hand_on_hip", aliases=("hand on hip",)),
            )
        )


@pytest.mark.asyncio
async def test_cleaned_resort_libraries_load_with_expected_counts_and_metadata() -> None:
    loaded = await FileSystemWorldpackLoader().load(
        RESORT_ROOT,
        session_id="visual-library-integration",
    )

    libraries = {
        "action_library": (loaded.action_library, 181),
        "pose_library": (loaded.pose_library, 99),
        "camera_library": (loaded.camera_library, 43),
        "lighting_library": (loaded.lighting_library, 31),
        "location_visual_library": (loaded.location_visual_library, 9),
        "outfit_library": (loaded.outfit_library, 221),
        "style_library": (loaded.style_library, 8),
    }

    for expected_id, (library, expected_count) in libraries.items():
        assert library.schema_version == 1
        assert library.library_id == expected_id
        assert len(library.entries) == expected_count
        assert all(entry.positive_fragment.strip() for entry in library.entries)

    assert loaded.location_visual_library.world_id == WorldpackId("resort_world")
    assert loaded.outfit_library.world_id == WorldpackId("resort_world")
    assert loaded.sex_library is not None
    assert loaded.sex_library.library_id == "sex_library"
    assert loaded.sex_library.content_rating == "adult_18_plus"
    assert len(loaded.sex_library.entries) == 151


def _assert_exact_aliases_are_unique(library: SemanticLibraryDocument) -> None:
    owners: dict[str, str] = {}
    for entry in library.entries:
        for alias in entry.aliases:
            key = " ".join(alias.strip().casefold().split())
            assert key not in owners, (
                f"ambiguous alias {alias!r}: {owners.get(key)!r} and {entry.entry_id!r}"
            )
            owners[key] = entry.entry_id


@pytest.mark.asyncio
async def test_cleaned_resort_libraries_have_no_exact_alias_ambiguity() -> None:
    loaded = await FileSystemWorldpackLoader().load(
        RESORT_ROOT,
        session_id="visual-library-alias-audit",
    )

    for library in (
        loaded.action_library,
        loaded.pose_library,
        loaded.camera_library,
        loaded.lighting_library,
        loaded.location_visual_library,
        loaded.outfit_library,
        loaded.style_library,
    ):
        _assert_exact_aliases_are_unique(library)


@pytest.mark.asyncio
async def test_plain_yaml_overrides_packaged_gzip_library(tmp_path: Path) -> None:
    copied = tmp_path / "resort_world"
    shutil.copytree(RESORT_ROOT, copied)
    compressed = copied / "style_library.yaml.gz"
    assert compressed.is_file()

    override = {
        "schema_version": 1,
        "library_id": "style_library",
        "description": "plain override",
        "entries": [
            {
                "entry_id": "test_override_style",
                "description": "override style",
                "aliases": ["override"],
                "tags": ["test"],
                "positive_fragment": "override style fragment",
            }
        ],
    }
    (copied / "style_library.yaml").write_text(
        yaml.safe_dump(override, sort_keys=False),
        encoding="utf-8",
    )

    loaded = await FileSystemWorldpackLoader().load(
        copied,
        session_id="plain-library-override",
    )

    assert tuple(entry.entry_id for entry in loaded.style_library.entries) == (
        "test_override_style",
    )


@pytest.mark.asyncio
async def test_world_bound_library_rejects_wrong_world_id(tmp_path: Path) -> None:
    copied = tmp_path / "resort_world"
    shutil.copytree(RESORT_ROOT, copied)
    compressed = copied / "outfit_library.yaml.gz"
    with gzip.open(compressed, mode="rt", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle.read())
    payload["world_id"] = "different_world"
    (copied / "outfit_library.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(WorldpackValidationError, match="world_id"):
        await FileSystemWorldpackLoader().load(copied, session_id="wrong-world-library")


@pytest.mark.asyncio
async def test_adult_library_schema_is_gated_and_loaded_separately() -> None:
    adult = AdultSemanticLibraryDocument.model_validate(
        {
            "schema_version": 1,
            "library_id": "adult_visual_library",
            "description": "gated adult-only visual vocabulary",
            "content_rating": "adult_18_plus",
            "entries": [],
        }
    )

    assert adult.content_rating == "adult_18_plus"
    assert adult.library_id == "adult_visual_library"

    loaded = await FileSystemWorldpackLoader().load(
        RESORT_ROOT,
        session_id="adult-library-gating",
    )
    assert loaded.sex_library is not None
    assert loaded.sex_library.content_rating == "adult_18_plus"
    assert len(loaded.sex_library.entries) == 151


def _canonical_with_outfit(item: OutfitItem) -> CanonicalVST:
    victoria = EntityId("victoria")
    subject = CanonicalSubject(
        entity_id=victoria,
        kind=SubjectKind.NPC,
        name="Victoria",
        role="resort_director",
        prominence=VSTSubjectProminence.PRIMARY,
        identity=CanonicalVisualIdentity(
            base_prompt="adult woman",
            role_prompt="resort director",
            visual_gender="woman",
            canonical_traits=("dark hair",),
        ),
        outfit=OutfitState(items=(item,)),
        visual_state=VisualState(),
    )
    return CanonicalVST(
        scene_id=SceneId("library-test:1"),
        worldpack_id=WorldpackId("resort_world"),
        time=SceneTime(turn_number=1, day=1, world_phase="day"),
        location=CanonicalLocation(location_id=LocationId("pool"), name="Pool"),
        subjects=(subject,),
        action=CanonicalAction(
            participants=(victoria,),
            semantic=ResolvedSemanticEntry(
                entry_id="standing",
                description="standing",
                positive_fragment="standing",
            ),
        ),
        visual_focus=CanonicalVisualFocus(
            subject_ids=(victoria,),
            intent=SemanticIntent(description="Victoria"),
        ),
        camera=CanonicalCamera(
            semantic=ResolvedSemanticEntry(
                entry_id="medium",
                description="medium shot",
                positive_fragment="medium shot",
            )
        ),
        lighting=VSTLightingIntent(intent=SemanticIntent(description="daylight")),
        style=VSTStyleIntent(intent=SemanticIntent(description="realism")),
        safety=VSTSafetyIntent(),
    )


def test_explicit_outfit_visual_entry_id_is_authoritative() -> None:
    library = SemanticLibraryDocument(
        entries=(
            SemanticLibraryEntry(
                entry_id="canonical_white_jacket",
                description="canonical white jacket",
                aliases=("white resort jacket",),
                tags=("jacket", "white"),
                positive_fragment="tailored white resort jacket",
            ),
        )
    )
    item = OutfitItem(
        item_id="victoria_jacket",
        name="White jacket",
        slot="torso",
        layer=2,
        coverage=("torso",),
        color="white",
        visual_entry_id="canonical_white_jacket",
    )
    config = WorldpackVisualConfig(
        outfit_library=library,
        profile=PromptCompilerProfile(),
    )

    prompt = SemanticPromptCompiler().compile(_canonical_with_outfit(item), config)

    assert "tailored white resort jacket" in prompt.positive_prompt


def test_missing_explicit_outfit_visual_entry_id_fails_closed() -> None:
    item = OutfitItem(
        item_id="victoria_jacket",
        name="White jacket",
        slot="torso",
        layer=2,
        coverage=("torso",),
        color="white",
        visual_entry_id="missing_visual_entry",
    )
    config = WorldpackVisualConfig(profile=PromptCompilerProfile())

    with pytest.raises(SemanticLibraryResolutionError, match="missing_visual_entry"):
        SemanticPromptCompiler().compile(_canonical_with_outfit(item), config)

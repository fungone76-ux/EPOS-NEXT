from __future__ import annotations

import pytest
from pydantic import ValidationError

from epos.application.visual.canonical import (
    SemanticLibraryResolutionError,
    SemanticLibraryResolver,
)
from epos.application.visual.vst import SemanticIntent
from epos.application.worldpacks.models import (
    SemanticLibraryDocument,
    SemanticLibraryEntry,
)


def _entry(entry_id: str, description: str, *tags: str) -> SemanticLibraryEntry:
    return SemanticLibraryEntry(
        entry_id=entry_id,
        description=description,
        tags=tuple(tags),
    )


def test_exact_entry_id_match_wins() -> None:
    library = SemanticLibraryDocument(
        entries=(
            _entry("standing_relaxed", "relaxed standing pose", "standing", "relaxed"),
            _entry("standing_guarded", "guarded standing pose", "standing", "guarded"),
        )
    )

    resolved = SemanticLibraryResolver().resolve(
        SemanticIntent(description="standing_relaxed"),
        library,
        library_name="pose",
    )

    assert resolved.entry_id == "standing_relaxed"


def test_exact_description_match_is_case_and_whitespace_insensitive() -> None:
    library = SemanticLibraryDocument(
        entries=(
            _entry("pool_conversation", "Conversation beside the pool", "conversation", "pool"),
        )
    )

    resolved = SemanticLibraryResolver().resolve(
        SemanticIntent(description="  conversation   beside THE pool  "),
        library,
        library_name="action",
    )

    assert resolved.entry_id == "pool_conversation"


def test_tag_and_lexical_overlap_resolves_deterministically() -> None:
    library = SemanticLibraryDocument(
        entries=(
            _entry("seated_chat", "seated conversation", "seated", "conversation"),
            _entry("pool_chat", "conversation beside pool", "pool", "conversation"),
        )
    )

    resolved = SemanticLibraryResolver().resolve(
        SemanticIntent(
            description="conversation near pool",
            tags=("pool", "conversation"),
        ),
        library,
        library_name="action",
    )

    assert resolved.entry_id == "pool_chat"


def test_no_semantic_match_fails_closed() -> None:
    library = SemanticLibraryDocument(
        entries=(_entry("seated_chat", "seated conversation", "seated"),)
    )

    with pytest.raises(SemanticLibraryResolutionError, match="no match"):
        SemanticLibraryResolver().resolve(
            SemanticIntent(description="running through rain", tags=("running", "rain")),
            library,
            library_name="action",
        )


def test_single_generic_word_overlap_is_below_confidence_threshold() -> None:
    library = SemanticLibraryDocument(
        entries=(
            _entry("standing_poolside", "standing beside pool", "standing", "pool"),
        )
    )

    with pytest.raises(SemanticLibraryResolutionError, match="no match"):
        SemanticLibraryResolver().resolve(
            SemanticIntent(description="standing near doorway"),
            library,
            library_name="pose",
        )


def test_equal_best_non_camera_matches_are_ambiguous() -> None:
    library = SemanticLibraryDocument(
        entries=(
            _entry("pose_a", "medium stance", "medium"),
            _entry("pose_b", "medium posture", "medium"),
        )
    )

    with pytest.raises(SemanticLibraryResolutionError, match="ambiguous"):
        SemanticLibraryResolver().resolve(
            SemanticIntent(description="medium view", tags=("medium",)),
            library,
            library_name="pose",
        )


def test_ambiguous_camera_prefers_worldpack_medium_shot_fallback() -> None:
    library = SemanticLibraryDocument(
        entries=(
            _entry("extreme_wide_shot", "extreme wide shot", "wide"),
            _entry("wide_shot", "wide shot", "wide"),
            _entry("medium_shot", "medium shot", "medium"),
        )
    )

    resolved = SemanticLibraryResolver().resolve(
        SemanticIntent(description="wide view", tags=("wide",)),
        library,
        library_name="camera",
    )

    assert resolved.entry_id == "medium_shot"


def test_unknown_style_uses_authored_worldpack_fallback() -> None:
    library = SemanticLibraryDocument(
        entries=(
            _entry("cinematic_realism", "cinematic realistic image", "cinematic"),
            _entry("editorial", "editorial photography", "editorial"),
        )
    )

    resolved = SemanticLibraryResolver().resolve(
        SemanticIntent(description="luxury conversational portrait"),
        library,
        library_name="style",
    )

    assert resolved.entry_id == "cinematic_realism"


def test_unknown_lighting_uses_authored_worldpack_fallback() -> None:
    library = SemanticLibraryDocument(
        entries=(
            _entry("soft_ambient", "soft ambient light", "soft", "ambient"),
            _entry("hard_flash", "hard flash", "flash"),
        )
    )

    resolved = SemanticLibraryResolver().resolve(
        SemanticIntent(description="pleasant lobby illumination"),
        library,
        library_name="lighting",
    )

    assert resolved.entry_id == "soft_ambient"


def test_semantic_library_rejects_normalized_duplicate_entry_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate semantic library entry"):
        SemanticLibraryDocument(
            entries=(
                _entry("Same", "first"),
                _entry(" same ", "second"),
            )
        )

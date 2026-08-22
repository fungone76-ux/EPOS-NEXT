from __future__ import annotations

import pytest

from epos.application.visual.canonical import (
    SemanticLibraryResolutionError,
    VisualCanonicalizer,
)
from epos.application.visual.vst import SemanticIntent
from epos.application.worldpacks.models import SemanticLibraryDocument


class _AmbiguousActionResolver:
    def resolve(self, intent, library, *, library_name):
        del intent, library
        raise SemanticLibraryResolutionError(
            f"ambiguous {library_name} library match: physical_a, physical_b"
        )

    def resolve_components(self, intents, library, *, library_name):
        del intents, library
        raise SemanticLibraryResolutionError(
            f"ambiguous {library_name} library match: component_a, component_b"
        )


def test_dialogue_is_authorized_for_neutral_visual_action_fallback() -> None:
    assert VisualCanonicalizer._is_social_action("dialogue") is True
    assert VisualCanonicalizer._is_social_action("greeting") is True
    assert VisualCanonicalizer._is_social_action("move") is False


def test_ambiguous_social_scene_action_becomes_no_physical_action() -> None:
    canonicalizer = VisualCanonicalizer(resolver=_AmbiguousActionResolver())

    resolved = canonicalizer._resolve_scene_action(
        SemanticIntent(description="Victoria responds to the greeting"),
        SemanticLibraryDocument(),
        allow_social_fallback=True,
    )

    assert resolved.entry_id == "no_specific_physical_action"
    assert resolved.description == ""
    assert resolved.positive_fragment == ""


def test_ambiguous_social_subject_action_is_dropped() -> None:
    canonicalizer = VisualCanonicalizer(resolver=_AmbiguousActionResolver())

    resolved = canonicalizer._resolve_optional_action(
        SemanticIntent(description="Victoria acknowledges the player"),
        SemanticLibraryDocument(),
        allow_social_fallback=True,
    )

    assert resolved is None


def test_ambiguous_physical_action_still_fails_closed() -> None:
    canonicalizer = VisualCanonicalizer(resolver=_AmbiguousActionResolver())

    with pytest.raises(SemanticLibraryResolutionError, match="ambiguous action"):
        canonicalizer._resolve_scene_action(
            SemanticIntent(description="Victoria grabs the player's arm"),
            SemanticLibraryDocument(),
            allow_social_fallback=False,
        )

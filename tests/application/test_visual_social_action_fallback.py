from __future__ import annotations

import pytest

from epos.application.visual.canonical import (
    ResolvedSemanticEntry,
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


class _HandshakeResolver:
    def resolve(self, intent, library, *, library_name):
        del intent, library, library_name
        return ResolvedSemanticEntry(
            entry_id="shaking_hands",
            description="two subjects shaking hands",
            tags=("greeting", "physical"),
            positive_fragment="shaking hands",
        )

    def resolve_components(self, intents, library, *, library_name):
        del intents, library, library_name
        raise AssertionError("not used in this regression test")


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


def test_social_greeting_does_not_resolve_to_handshake_even_when_library_can_match() -> None:
    canonicalizer = VisualCanonicalizer(resolver=_HandshakeResolver())

    resolved = canonicalizer._resolve_scene_action(
        SemanticIntent(description="greet", tags=("greeting",)),
        SemanticLibraryDocument(),
        allow_social_fallback=True,
    )

    assert resolved.entry_id == "no_specific_physical_action"
    assert resolved.positive_fragment == ""


def test_ambiguous_social_subject_action_is_dropped() -> None:
    canonicalizer = VisualCanonicalizer(resolver=_AmbiguousActionResolver())

    resolved = canonicalizer._resolve_optional_action(
        SemanticIntent(description="Victoria acknowledges the player"),
        SemanticLibraryDocument(),
        allow_social_fallback=True,
    )

    assert resolved is None


def test_social_subject_action_is_dropped_even_when_it_matches_physical_library() -> None:
    canonicalizer = VisualCanonicalizer(resolver=_HandshakeResolver())

    resolved = canonicalizer._resolve_optional_action(
        SemanticIntent(description="shakes the player's hand"),
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

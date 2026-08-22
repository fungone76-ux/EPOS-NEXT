"""Deterministic semantic-library resolution for visual canonicalization."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol

from epos.application.visual.canonical.errors import SemanticLibraryResolutionError
from epos.application.visual.canonical.models import ResolvedSemanticEntry
from epos.application.visual.vst import SemanticIntent
from epos.application.worldpacks.models import (
    SemanticLibraryDocument,
    SemanticLibraryEntry,
)

_WORD = re.compile(r"[a-z0-9]+")
_CAMERA_FALLBACK_PRIORITY = (
    "medium_eye_level",
    "medium_shot",
    "medium",
    "waist_up",
    "close_up",
    "wide_shot",
)
_NON_BLOCKING_LIBRARIES = frozenset({"style", "lighting"})


class SemanticResolverProtocol(Protocol):
    def resolve(
        self,
        intent: SemanticIntent,
        library: SemanticLibraryDocument,
        *,
        library_name: str,
    ) -> ResolvedSemanticEntry: ...

    def resolve_components(
        self,
        intents: Sequence[SemanticIntent],
        library: SemanticLibraryDocument,
        *,
        library_name: str,
    ) -> ResolvedSemanticEntry: ...


class SemanticLibraryResolver:
    """Resolve only evidence supported by the current Worldpack library schema."""

    def resolve(
        self,
        intent: SemanticIntent,
        library: SemanticLibraryDocument,
        *,
        library_name: str,
    ) -> ResolvedSemanticEntry:
        return self.resolve_components((intent,), library, library_name=library_name)

    def resolve_components(
        self,
        intents: Sequence[SemanticIntent],
        library: SemanticLibraryDocument,
        *,
        library_name: str,
    ) -> ResolvedSemanticEntry:
        if not intents:
            raise SemanticLibraryResolutionError(
                f"no semantic intent supplied for {library_name} library"
            )

        descriptions = tuple(self._normalize_text(item.description) for item in intents)
        combined_description = " ".join(descriptions)
        combined_tags = {tag.casefold() for item in intents for tag in item.tags}
        query_words = self._words(combined_description)

        if len(intents) == 1:
            exact_id = [
                entry
                for entry in library.entries
                if entry.entry_id.strip().casefold() == descriptions[0]
            ]
            if exact_id:
                return self._require_single(exact_id, library_name, "exact id")

            exact_alias = [
                entry
                for entry in library.entries
                if descriptions[0]
                in {self._normalize_text(alias) for alias in entry.aliases}
            ]
            if exact_alias:
                return self._require_single(exact_alias, library_name, "exact alias")

            exact_positive_fragment = [
                entry
                for entry in library.entries
                if entry.positive_fragment.strip()
                and self._normalize_text(entry.positive_fragment) == descriptions[0]
            ]
            if exact_positive_fragment:
                return self._require_single(
                    exact_positive_fragment,
                    library_name,
                    "exact positive fragment",
                )

        exact_description = [
            entry
            for entry in library.entries
            if self._normalize_text(entry.description) == combined_description
        ]
        if exact_description:
            return self._require_single(
                exact_description,
                library_name,
                "exact description",
            )

        scored: list[tuple[int, SemanticLibraryEntry]] = []
        for entry in library.entries:
            entry_tags = {tag.casefold() for tag in entry.tags}
            tag_overlap = len(combined_tags & entry_tags)
            authored_text = " ".join(
                (entry.description, *entry.aliases, entry.positive_fragment)
            )
            lexical_overlap = len(query_words & self._words(authored_text))
            if tag_overlap == 0 and lexical_overlap < 2:
                continue
            score = (tag_overlap * 10) + lexical_overlap
            scored.append((score, entry))

        if not scored:
            aesthetic = self._aesthetic_fallback(library, library_name)
            if aesthetic is not None:
                return aesthetic
            raise SemanticLibraryResolutionError(
                f"no match in {library_name} library for semantic intent"
            )

        best_score = max(score for score, _entry in scored)
        best = [entry for score, entry in scored if score == best_score]
        if len(best) != 1:
            if library_name == "camera":
                return self._resolved(self._camera_fallback(library.entries))
            if library_name in _NON_BLOCKING_LIBRARIES:
                return self._resolved(min(best, key=lambda entry: entry.entry_id.casefold()))
            ids = ", ".join(sorted(entry.entry_id for entry in best))
            raise SemanticLibraryResolutionError(
                f"ambiguous {library_name} library match: {ids}"
            )
        return self._resolved(best[0])

    def _aesthetic_fallback(
        self,
        library: SemanticLibraryDocument,
        library_name: str,
    ) -> ResolvedSemanticEntry | None:
        if library_name not in _NON_BLOCKING_LIBRARIES or not library.entries:
            return None
        preferred_tokens = (
            ("neutral", "natural", "cinematic", "realistic")
            if library_name == "style"
            else ("natural", "ambient", "soft", "neutral")
        )
        for token in preferred_tokens:
            for entry in library.entries:
                authored = " ".join(
                    (entry.entry_id, entry.description, *entry.aliases, *entry.tags)
                ).casefold()
                if token in authored:
                    return self._resolved(entry)
        return self._resolved(min(library.entries, key=lambda entry: entry.entry_id.casefold()))

    @classmethod
    def _camera_fallback(
        cls,
        entries: Sequence[SemanticLibraryEntry],
    ) -> SemanticLibraryEntry:
        if not entries:
            raise SemanticLibraryResolutionError(
                "cannot choose camera fallback from an empty library"
            )
        normalized = {entry.entry_id.strip().casefold(): entry for entry in entries}
        for preferred in _CAMERA_FALLBACK_PRIORITY:
            entry = normalized.get(preferred)
            if entry is not None:
                return entry
        return min(entries, key=lambda entry: entry.entry_id.strip().casefold())

    @classmethod
    def _words(cls, value: str) -> set[str]:
        return set(_WORD.findall(cls._normalize_text(value)))

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(value.strip().casefold().split())

    def _require_single(
        self,
        entries: list[SemanticLibraryEntry],
        library_name: str,
        match_kind: str,
    ) -> ResolvedSemanticEntry:
        if len(entries) != 1:
            if library_name == "camera":
                return self._resolved(self._camera_fallback(entries))
            if library_name in _NON_BLOCKING_LIBRARIES:
                return self._resolved(min(entries, key=lambda entry: entry.entry_id.casefold()))
            ids = ", ".join(sorted(entry.entry_id for entry in entries))
            raise SemanticLibraryResolutionError(
                f"ambiguous {library_name} {match_kind} match: {ids}"
            )
        return self._resolved(entries[0])

    @staticmethod
    def _resolved(entry: SemanticLibraryEntry) -> ResolvedSemanticEntry:
        return ResolvedSemanticEntry(
            entry_id=entry.entry_id,
            description=entry.description,
            tags=entry.tags,
            positive_fragment=entry.positive_fragment,
        )

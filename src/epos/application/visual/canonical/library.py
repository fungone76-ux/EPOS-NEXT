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
            authored_text = " ".join((entry.description, *entry.aliases))
            lexical_overlap = len(query_words & self._words(authored_text))
            if tag_overlap == 0 and lexical_overlap < 2:
                continue
            score = (tag_overlap * 10) + lexical_overlap
            scored.append((score, entry))

        if not scored:
            raise SemanticLibraryResolutionError(
                f"no match in {library_name} library for semantic intent"
            )

        best_score = max(score for score, _entry in scored)
        best = [entry for score, entry in scored if score == best_score]
        if len(best) != 1:
            ids = ", ".join(sorted(entry.entry_id for entry in best))
            raise SemanticLibraryResolutionError(
                f"ambiguous {library_name} library match: {ids}"
            )
        return self._resolved(best[0])

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

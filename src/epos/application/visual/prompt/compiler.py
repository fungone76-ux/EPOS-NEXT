"""Deterministic CanonicalVST -> Stable Diffusion prompt compilation."""

from __future__ import annotations

import re
from collections.abc import Iterable

from epos.application.visual.canonical import (
    CanonicalSubject,
    CanonicalVST,
    ResolvedLora,
    ResolvedSemanticEntry,
    SemanticLibraryResolutionError,
    SemanticLibraryResolver,
)
from epos.application.visual.prompt.constants import FIXED_NEGATIVE_PROMPT
from epos.application.visual.prompt.models import (
    PromptCompilerProfile,
    RenderPromptContract,
    SubjectCountRule,
    WorldpackVisualConfig,
)
from epos.application.visual.vst import SemanticIntent
from epos.application.worldpacks.models import (
    SemanticLibraryDocument,
    SemanticLibraryEntry,
)
from epos.domain.outfit import OutfitItem

_WORD = re.compile(r"[a-z]+")


class SemanticPromptCompiler:
    """Compile only Python-authorized canonical visual data into render prompts."""

    def __init__(self, resolver: SemanticLibraryResolver | None = None) -> None:
        self._resolver = resolver or SemanticLibraryResolver()

    def compile(
        self,
        canonical_vst: CanonicalVST,
        config: WorldpackVisualConfig,
    ) -> RenderPromptContract:
        profile = config.profile
        fragments: list[str] = []
        fragments.extend(profile.quality_layer)
        fragments.extend(self._style_fragments(canonical_vst, config))
        fragments.extend(config.world_positive)
        fragments.extend(self._location_fragments(canonical_vst, config))
        fragments.append(canonical_vst.time.world_phase)
        fragments.extend(self._subject_count_fragments(canonical_vst, profile))

        for subject in canonical_vst.subjects:
            fragments.extend(self._subject_fragments(subject, config.outfit_library))

        fragments.append(self._semantic_fragment(canonical_vst.action.semantic))
        fragments.extend(self._focus_fragments(canonical_vst))
        fragments.append(self._semantic_fragment(canonical_vst.camera.semantic))
        fragments.extend(self._lighting_fragments(canonical_vst, config))

        return RenderPromptContract(
            positive_prompt=self._compile_atoms(fragments),
            negative_prompt=FIXED_NEGATIVE_PROMPT,
            loras=self._resolved_loras(canonical_vst),
            checkpoint=profile.checkpoint,
            width=profile.width,
            height=profile.height,
            sampler=profile.sampler,
            scheduler=profile.scheduler,
            steps=profile.steps,
            cfg=profile.cfg,
        )

    def _style_fragments(
        self,
        canonical_vst: CanonicalVST,
        config: WorldpackVisualConfig,
    ) -> tuple[str, ...]:
        entry = self._resolve_if_configured(
            canonical_vst.style.intent,
            config.style_library,
            library_name="style",
        )
        return () if entry is None else (self._semantic_fragment(entry),)

    def _location_fragments(
        self,
        canonical_vst: CanonicalVST,
        config: WorldpackVisualConfig,
    ) -> tuple[str, ...]:
        if not config.location_visual_library.entries:
            return (canonical_vst.location.name,)
        entry = self._resolver.resolve(
            SemanticIntent(description=str(canonical_vst.location.location_id)),
            config.location_visual_library,
            library_name="location_visual",
        )
        return (self._semantic_fragment(entry),)

    def _lighting_fragments(
        self,
        canonical_vst: CanonicalVST,
        config: WorldpackVisualConfig,
    ) -> tuple[str, ...]:
        entry = self._resolve_if_configured(
            canonical_vst.lighting.intent,
            config.lighting_library,
            library_name="lighting",
        )
        return () if entry is None else (self._semantic_fragment(entry),)

    def _subject_fragments(
        self,
        subject: CanonicalSubject,
        outfit_library: SemanticLibraryDocument,
    ) -> tuple[str, ...]:
        fragments: list[str] = [
            subject.identity.base_prompt,
            subject.identity.role_prompt,
            *subject.identity.canonical_traits,
        ]
        for item in subject.outfit.ordered_items():
            fragments.append(self._outfit_fragment(item, outfit_library))
        fragments.extend(self._visual_state_fragments(subject))
        if subject.pose is not None:
            fragments.append(self._semantic_fragment(subject.pose))
        if subject.action is not None:
            fragments.append(self._semantic_fragment(subject.action))
        if subject.body_orientation is not None:
            fragments.append(self._semantic_fragment(subject.body_orientation))
        return tuple(fragment for fragment in fragments if fragment.strip())

    def _outfit_fragment(
        self,
        item: OutfitItem,
        library: SemanticLibraryDocument,
    ) -> str:
        authored = self._find_outfit_entry(item, library)
        if authored is not None:
            return self._entry_fragment(authored)

        parts = tuple(
            value
            for value in (item.color, item.material, item.name, item.state)
            if value is not None and value.strip() and value.casefold() != "dry"
        )
        return " ".join(parts)

    @staticmethod
    def _find_outfit_entry(
        item: OutfitItem,
        library: SemanticLibraryDocument,
    ) -> SemanticLibraryEntry | None:
        if item.visual_entry_id is not None:
            target = item.visual_entry_id.strip().casefold()
            for entry in library.entries:
                if entry.entry_id.strip().casefold() == target:
                    return entry
            raise SemanticLibraryResolutionError(
                "no match in outfit library for explicit visual_entry_id: "
                f"{item.visual_entry_id}"
            )

        targets = {item.item_id.strip().casefold(), item.name.strip().casefold()}
        for entry in library.entries:
            authored_names = {
                entry.entry_id.strip().casefold(),
                entry.description.strip().casefold(),
                *(alias.strip().casefold() for alias in entry.aliases),
            }
            if targets & authored_names:
                return entry
        return None

    @classmethod
    def _visual_state_fragments(cls, subject: CanonicalSubject) -> tuple[str, ...]:
        fragments: list[str] = []
        for key in sorted(subject.visual_state.traits):
            if cls._visual_state_key_is_forbidden(key):
                continue
            value = subject.visual_state.traits[key]
            label = key.replace("_", " ").strip()
            if value is True:
                fragments.append(label)
            elif isinstance(value, str) and value.strip():
                fragments.append(f"{label} {value.strip()}")
        return tuple(fragments)

    @staticmethod
    def _visual_state_key_is_forbidden(key: str) -> bool:
        normalized = key.casefold().replace("-", "_")
        forbidden_tokens = (
            "face",
            "facial",
            "expression",
            "smile",
            "frown",
            "mouth",
            "eyebrow",
            "mood",
            "emotion",
            "posture",
        )
        return any(token in normalized for token in forbidden_tokens)

    def _subject_count_fragments(
        self,
        canonical_vst: CanonicalVST,
        profile: PromptCompilerProfile,
    ) -> tuple[str, ...]:
        counts: dict[str, int] = {}
        for subject in canonical_vst.subjects:
            gender = subject.identity.visual_gender.strip().casefold()
            counts[gender] = counts.get(gender, 0) + 1

        rules = {rule.visual_gender.strip().casefold(): rule for rule in profile.count_rules}
        return tuple(
            self._render_count_tag(gender, count, rules.get(gender))
            for gender, count in counts.items()
        )

    @staticmethod
    def _render_count_tag(
        gender: str,
        count: int,
        rule: SubjectCountRule | None,
    ) -> str:
        if rule is None:
            suffix = gender if count == 1 else f"{gender}s"
            return f"{count}{suffix}"
        if count == 1:
            return rule.singular_tag
        return rule.plural_tag_template.format(count=count)

    @staticmethod
    def _focus_fragments(canonical_vst: CanonicalVST) -> tuple[str, ...]:
        by_id = {subject.entity_id: subject for subject in canonical_vst.subjects}
        genders = tuple(
            by_id[subject_id].identity.visual_gender.strip().casefold()
            for subject_id in canonical_vst.visual_focus.subject_ids
        )
        if not genders:
            return ()
        if len(genders) == 1:
            return (f"focus on {genders[0]}",)
        return (f"focus on {' and '.join(genders)}",)

    @staticmethod
    def _resolved_loras(canonical_vst: CanonicalVST) -> tuple[ResolvedLora, ...]:
        resolved: list[ResolvedLora] = []
        seen: set[tuple[str, str]] = set()
        for subject in canonical_vst.subjects:
            lora = subject.lora
            if lora is None:
                continue
            key = (lora.alias, lora.filename)
            if key in seen:
                continue
            seen.add(key)
            resolved.append(lora.model_copy(deep=True))
        return tuple(resolved)

    def _resolve_if_configured(
        self,
        intent: SemanticIntent,
        library: SemanticLibraryDocument,
        *,
        library_name: str,
    ) -> ResolvedSemanticEntry | None:
        if not library.entries:
            return None
        return self._resolver.resolve(intent, library, library_name=library_name)

    @staticmethod
    def _entry_fragment(entry: SemanticLibraryEntry) -> str:
        return entry.positive_fragment.strip() or entry.description.strip()

    @staticmethod
    def _semantic_fragment(entry: ResolvedSemanticEntry) -> str:
        return entry.positive_fragment.strip() or entry.description.strip()

    @classmethod
    def _compile_atoms(cls, fragments: Iterable[str]) -> str:
        atoms: list[str] = []
        seen: set[str] = set()
        for fragment in fragments:
            for raw_atom in fragment.split(","):
                atom = " ".join(raw_atom.strip().split())
                if not atom or cls._is_facial_expression_atom(atom):
                    continue
                key = atom.casefold()
                if key in seen:
                    continue
                seen.add(key)
                atoms.append(atom)
        return ", ".join(atoms)

    @staticmethod
    def _is_facial_expression_atom(atom: str) -> bool:
        words = set(_WORD.findall(atom.casefold()))
        direct_cues = {
            "expression",
            "expressions",
            "smile",
            "smiles",
            "smiling",
            "frown",
            "frowning",
            "grin",
            "grinning",
            "smirk",
            "smirking",
            "blush",
            "blushing",
            "mouth",
            "eyebrow",
            "eyebrows",
        }
        if words & direct_cues:
            return True
        if "face" in words and words & {
            "angry",
            "sad",
            "happy",
            "seductive",
            "serious",
            "neutral",
        }:
            return True
        return "furrowed" in words and bool(words & {"brow", "brows"})

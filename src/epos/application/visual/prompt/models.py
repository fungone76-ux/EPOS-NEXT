"""Strict deterministic prompt contracts for Module 13."""

from __future__ import annotations

from pydantic import Field

from epos.application.visual.canonical import ResolvedLora
from epos.application.worldpacks.models import LoadedWorldpack, SemanticLibraryDocument
from epos.domain.base import DomainModel


class SubjectCountRule(DomainModel):
    visual_gender: str
    singular_tag: str
    plural_tag_template: str


_DEFAULT_COUNT_RULES = (
    SubjectCountRule(
        visual_gender="woman",
        singular_tag="1woman",
        plural_tag_template="{count}women",
    ),
    SubjectCountRule(
        visual_gender="man",
        singular_tag="1man",
        plural_tag_template="{count}men",
    ),
    SubjectCountRule(
        visual_gender="person",
        singular_tag="1person",
        plural_tag_template="{count}people",
    ),
)


class PromptCompilerProfile(DomainModel):
    quality_layer: tuple[str, ...] = ()
    count_rules: tuple[SubjectCountRule, ...] = _DEFAULT_COUNT_RULES
    checkpoint: str | None = None
    width: int = Field(default=896, ge=64)
    height: int = Field(default=1152, ge=64)
    sampler: str | None = None
    scheduler: str | None = None
    steps: int | None = Field(default=None, ge=1)
    cfg: float | None = Field(default=None, gt=0)


class WorldpackVisualConfig(DomainModel):
    world_positive: tuple[str, ...] = ()
    outfit_library: SemanticLibraryDocument = Field(default_factory=SemanticLibraryDocument)
    lighting_library: SemanticLibraryDocument = Field(default_factory=SemanticLibraryDocument)
    location_visual_library: SemanticLibraryDocument = Field(
        default_factory=SemanticLibraryDocument
    )
    style_library: SemanticLibraryDocument = Field(default_factory=SemanticLibraryDocument)
    profile: PromptCompilerProfile = Field(default_factory=PromptCompilerProfile)

    @classmethod
    def from_loaded_worldpack(
        cls,
        worldpack: LoadedWorldpack,
        *,
        profile: PromptCompilerProfile,
    ) -> WorldpackVisualConfig:
        """Build an isolated compiler view from the active loaded Worldpack."""
        return cls(
            world_positive=tuple(worldpack.visual.world_positive),
            outfit_library=worldpack.outfit_library.model_copy(deep=True),
            lighting_library=worldpack.lighting_library.model_copy(deep=True),
            location_visual_library=worldpack.location_visual_library.model_copy(deep=True),
            style_library=worldpack.style_library.model_copy(deep=True),
            profile=profile.model_copy(deep=True),
        )


class RenderPromptContract(DomainModel):
    positive_prompt: str
    negative_prompt: str
    loras: tuple[ResolvedLora, ...] = ()
    checkpoint: str | None = None
    width: int = Field(ge=64)
    height: int = Field(ge=64)
    sampler: str | None = None
    scheduler: str | None = None
    steps: int | None = Field(default=None, ge=1)
    cfg: float | None = Field(default=None, gt=0)

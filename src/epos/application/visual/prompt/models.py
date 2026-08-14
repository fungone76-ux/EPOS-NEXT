"""Strict deterministic prompt contracts for Module 13."""

from __future__ import annotations

from pydantic import Field

from epos.application.visual.canonical import ResolvedLora
from epos.application.worldpacks.models import SemanticLibraryDocument
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

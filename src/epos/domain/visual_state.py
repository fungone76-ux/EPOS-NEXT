"""Persistent observable visual conditions distinct from outfit."""

from pydantic import Field, JsonValue

from epos.domain.base import DomainModel


class VisualState(DomainModel):
    traits: dict[str, JsonValue] = Field(default_factory=dict)

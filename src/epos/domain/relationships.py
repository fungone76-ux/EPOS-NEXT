"""Persistent multidimensional relationship state."""

from pydantic import Field

from epos.domain.base import DomainModel


class RelationshipState(DomainModel):
    trust: float = Field(default=0.0, ge=-10.0, le=10.0)
    fear: float = Field(default=0.0, ge=-10.0, le=10.0)
    attraction: float = Field(default=0.0, ge=-10.0, le=10.0)
    affection: float = Field(default=0.0, ge=-10.0, le=10.0)
    resentment: float = Field(default=0.0, ge=-10.0, le=10.0)
    dependency: float = Field(default=0.0, ge=-10.0, le=10.0)
    respect: float = Field(default=0.0, ge=-10.0, le=10.0)
    suspicion: float = Field(default=0.0, ge=-10.0, le=10.0)

"""Persistent emotional state only; behavioral engines live in later modules."""

from pydantic import Field

from epos.domain.base import DomainModel


class EmotionalState(DomainModel):
    joy: float = Field(default=0.0, ge=0.0, le=10.0)
    anger: float = Field(default=0.0, ge=0.0, le=10.0)
    fear: float = Field(default=0.0, ge=0.0, le=10.0)
    sadness: float = Field(default=0.0, ge=0.0, le=10.0)
    curiosity: float = Field(default=0.0, ge=0.0, le=10.0)
    attraction: float = Field(default=0.0, ge=0.0, le=10.0)
    jealousy: float = Field(default=0.0, ge=0.0, le=10.0)
    shame: float = Field(default=0.0, ge=0.0, le=10.0)
    melancholy: float = Field(default=0.0, ge=0.0, le=10.0)

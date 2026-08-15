"""Persistent general bond plus a separate Python-derived emergent-love phase."""

from enum import StrEnum

from epos.domain.base import DomainModel


class BondPhase(StrEnum):
    NONE = "none"
    FORMING = "forming"
    ESTABLISHED = "established"
    DEEP = "deep"


class LovePhase(StrEnum):
    NONE = "none"
    FALLING_IN_LOVE = "falling_in_love"
    IN_LOVE = "in_love"


class BondState(DomainModel):
    phase: BondPhase = BondPhase.NONE
    love_phase: LovePhase = LovePhase.NONE

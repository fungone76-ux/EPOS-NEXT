"""Persistent general bond state, independent from sexual intimacy or love."""

from enum import StrEnum

from epos.domain.base import DomainModel


class BondPhase(StrEnum):
    NONE = "none"
    FORMING = "forming"
    ESTABLISHED = "established"
    DEEP = "deep"


class BondState(DomainModel):
    phase: BondPhase = BondPhase.NONE

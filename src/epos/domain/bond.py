"""Persisted bond state; derivation rules belong to Module 03."""

from enum import StrEnum

from epos.domain.base import DomainModel


class BondPhase(StrEnum):
    NONE = "none"
    GROWING_BOND = "growing_bond"
    DEEP_BOND = "deep_bond"
    FALLING_IN_LOVE = "falling_in_love"
    IN_LOVE = "in_love"


class BondState(DomainModel):
    phase: BondPhase = BondPhase.NONE

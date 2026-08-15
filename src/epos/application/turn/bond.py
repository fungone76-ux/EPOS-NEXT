"""Conservative Python-owned bond/love derivation with progression and hysteresis."""

from __future__ import annotations

from dataclasses import dataclass

from epos.application.turn.models import BondDerivationContext
from epos.domain.bond import BondPhase, BondState, LovePhase


@dataclass(frozen=True, slots=True)
class _Threshold:
    trust: float
    affection: float
    attraction: float
    respect: float
    max_resentment: float
    max_fear: float
    core_memories: int
    turn: int
    day: int


_PROGRESSION: tuple[tuple[BondPhase, LovePhase], ...] = (
    (BondPhase.NONE, LovePhase.NONE),
    (BondPhase.FORMING, LovePhase.NONE),
    (BondPhase.ESTABLISHED, LovePhase.NONE),
    (BondPhase.DEEP, LovePhase.NONE),
    (BondPhase.DEEP, LovePhase.FALLING_IN_LOVE),
    (BondPhase.DEEP, LovePhase.IN_LOVE),
)

_THRESHOLDS = {
    (BondPhase.FORMING, LovePhase.NONE): _Threshold(
        3.0, 3.0, 1.0, 2.0, 4.0, 5.0, 0, 8, 1
    ),
    (BondPhase.ESTABLISHED, LovePhase.NONE): _Threshold(
        5.0, 5.0, 2.0, 4.0, 3.0, 4.0, 1, 16, 2
    ),
    (BondPhase.DEEP, LovePhase.NONE): _Threshold(7.0, 7.0, 4.0, 6.0, 2.0, 3.0, 2, 28, 4),
    (BondPhase.DEEP, LovePhase.FALLING_IN_LOVE): _Threshold(
        8.0, 8.0, 6.0, 7.0, 1.5, 2.0, 3, 44, 6
    ),
    (BondPhase.DEEP, LovePhase.IN_LOVE): _Threshold(
        9.0, 9.0, 7.0, 8.0, 1.0, 1.5, 5, 64, 9
    ),
}

_MEANINGFUL_EVENTS = frozenset(
    {"kindness", "promise_kept", "support", "romantic_milestone"}
)


class EmergentBondPolicy:
    """Advance at most one phase per observed event; never accepts an LLM phase proposal."""

    def derive(self, context: BondDerivationContext) -> BondState:
        current = (context.current_bond.phase, context.current_bond.love_phase)
        current_index = _PROGRESSION.index(current)

        if self._severe_blocker(context) and current_index > 0:
            phase, love_phase = _PROGRESSION[current_index - 1]
            return BondState(phase=phase, love_phase=love_phase)

        if current_index == len(_PROGRESSION) - 1:
            return context.current_bond.model_copy(deep=True)
        if not _MEANINGFUL_EVENTS.intersection(context.event_types):
            return context.current_bond.model_copy(deep=True)

        candidate = _PROGRESSION[current_index + 1]
        threshold = _THRESHOLDS[candidate]
        if self._meets(context, threshold):
            phase, love_phase = candidate
            return BondState(phase=phase, love_phase=love_phase)
        return context.current_bond.model_copy(deep=True)

    @staticmethod
    def _meets(context: BondDerivationContext, threshold: _Threshold) -> bool:
        relationship = context.relationship_with_player
        return (
            relationship.trust >= threshold.trust
            and relationship.affection >= threshold.affection
            and relationship.attraction >= threshold.attraction
            and relationship.respect >= threshold.respect
            and relationship.resentment <= threshold.max_resentment
            and relationship.fear <= threshold.max_fear
            and context.core_memory_count >= threshold.core_memories
            and context.turn_number >= threshold.turn
            and context.day >= threshold.day
        )

    @staticmethod
    def _severe_blocker(context: BondDerivationContext) -> bool:
        relationship = context.relationship_with_player
        return (
            relationship.trust < 0.0
            or relationship.resentment >= 7.0
            or relationship.fear >= 8.0
            or "betrayal" in context.event_types
        )

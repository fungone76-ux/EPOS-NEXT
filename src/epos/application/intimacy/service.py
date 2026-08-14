"""Deterministic NPC intimacy updates and explicit consent authorization."""

from epos.application.intimacy.models import (
    ConsentScope,
    ConsentSignal,
    ConsentStatus,
    IntimacyAuthorization,
    IntimacyAuthorizationRequest,
    IntimacyEffect,
    IntimacyEvent,
    IntimacyProfile,
)
from epos.application.intimacy.rules import default_effect_for
from epos.domain.errors import ContractError
from epos.domain.ids import EntityId, TurnNumber
from epos.domain.intimacy import IntimacyState


def _clamp(value: float) -> float:
    return max(0.0, min(10.0, value))


def _scaled(delta: float, intensity: float, sensitivity: float) -> float:
    return delta * intensity * sensitivity


def _consent_reasons(
    *,
    label: str,
    signal: ConsentSignal | None,
    actor_id: EntityId,
    partner_id: EntityId,
    scope: ConsentScope,
    turn: TurnNumber,
) -> tuple[str, ...]:
    if signal is None:
        return (f"missing_{label}_consent",)

    reasons: list[str] = []
    if signal.actor_id != actor_id:
        reasons.append(f"invalid_{label}_consent_actor")
    if signal.partner_id != partner_id:
        reasons.append(f"invalid_{label}_consent_partner")
    if signal.scope != scope:
        reasons.append(f"invalid_{label}_consent_scope")
    if signal.turn != turn:
        reasons.append(f"stale_{label}_consent")
    if signal.status is ConsentStatus.WITHDRAWN:
        reasons.append(f"{label}_consent_withdrawn")
    elif signal.status is not ConsentStatus.GRANTED:
        reasons.append(f"{label}_consent_not_granted")
    return tuple(reasons)


class IntimacyService:
    """Apply Python-owned rules without inferring consent from scores."""

    @classmethod
    def default(cls) -> "IntimacyService":
        return cls()

    def apply_event(
        self,
        *,
        state: IntimacyState,
        event: IntimacyEvent,
        profile: IntimacyProfile,
    ) -> IntimacyState:
        effect = default_effect_for(event.event_type)
        return self._apply_effect(state, effect, event.intensity, profile)

    def authorize(self, request: IntimacyAuthorizationRequest) -> IntimacyAuthorization:
        reasons: list[str] = []
        if not request.player_adult_verified:
            reasons.append("player_not_adult_verified")
        if not request.npc_adult_verified:
            reasons.append("npc_not_adult_verified")

        reasons.extend(
            _consent_reasons(
                label="player",
                signal=request.player_consent,
                actor_id=request.player_id,
                partner_id=request.npc_id,
                scope=request.scope,
                turn=request.current_turn,
            )
        )
        reasons.extend(
            _consent_reasons(
                label="npc",
                signal=request.npc_consent,
                actor_id=request.npc_id,
                partner_id=request.player_id,
                scope=request.scope,
                turn=request.current_turn,
            )
        )
        return IntimacyAuthorization(
            allowed=not reasons,
            scope=request.scope,
            turn=request.current_turn,
            reasons=tuple(reasons),
        )

    def record_completed_sexual_activity(
        self,
        *,
        state: IntimacyState,
        authorization: IntimacyAuthorization,
        turn: TurnNumber,
    ) -> IntimacyState:
        if (
            not authorization.allowed
            or authorization.scope is not ConsentScope.SEXUAL_ACTIVITY
            or authorization.turn != turn
        ):
            raise ContractError(
                "sexual activity not authorized",
                code="intimacy.not_authorized",
            )
        return IntimacyState(
            sexual_attraction=state.sexual_attraction,
            desire=state.desire,
            arousal=state.arousal,
            comfort=state.comfort,
            tension=state.tension,
            completed_sexual_encounters=state.completed_sexual_encounters + 1,
            last_intimate_turn=turn,
        )

    @staticmethod
    def _apply_effect(
        state: IntimacyState,
        effect: IntimacyEffect,
        intensity: float,
        profile: IntimacyProfile,
    ) -> IntimacyState:
        return IntimacyState(
            sexual_attraction=_clamp(
                state.sexual_attraction
                + _scaled(
                    effect.sexual_attraction,
                    intensity,
                    profile.sexual_attraction_sensitivity,
                )
            ),
            desire=_clamp(
                state.desire + _scaled(effect.desire, intensity, profile.desire_sensitivity)
            ),
            arousal=_clamp(
                state.arousal + _scaled(effect.arousal, intensity, profile.arousal_sensitivity)
            ),
            comfort=_clamp(
                state.comfort + _scaled(effect.comfort, intensity, profile.comfort_sensitivity)
            ),
            tension=_clamp(
                state.tension + _scaled(effect.tension, intensity, profile.tension_sensitivity)
            ),
            completed_sexual_encounters=state.completed_sexual_encounters,
            last_intimate_turn=state.last_intimate_turn,
        )

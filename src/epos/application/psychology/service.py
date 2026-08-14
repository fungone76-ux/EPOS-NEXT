"""Deterministic psychology and relationship update service."""

from epos.application.psychology.models import (
    EmotionEffect,
    PsychologicalEvent,
    PsychologicalUpdate,
    PsychologyProfile,
    RelationshipEffect,
)
from epos.application.psychology.rules import default_rule_for
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _scaled(delta: float, intensity: float, sensitivity: float) -> float:
    return delta * intensity * sensitivity


def _decay(value: float, rate: float, elapsed_time_units: float) -> float:
    return _clamp(value - (rate * elapsed_time_units), 0.0, 10.0)


class PsychologyService:
    """Apply Python-owned psychological rules to validated domain state."""

    @classmethod
    def default(cls) -> "PsychologyService":
        return cls()

    def apply_event(
        self,
        *,
        event: PsychologicalEvent,
        emotions: EmotionalState,
        relationship: RelationshipState,
        profile: PsychologyProfile,
    ) -> PsychologicalUpdate:
        rule = default_rule_for(event.event_type)
        return PsychologicalUpdate(
            emotions=self._apply_emotion_effect(emotions, rule.emotions, event.intensity, profile),
            relationship=self._apply_relationship_effect(
                relationship,
                rule.relationship,
                event.intensity,
                profile,
            ),
        )

    def decay_emotions(
        self,
        state: EmotionalState,
        *,
        elapsed_time_units: float,
        profile: PsychologyProfile,
    ) -> EmotionalState:
        if elapsed_time_units < 0.0:
            raise ValueError("elapsed_time_units must be non-negative")
        if elapsed_time_units == 0.0:
            return state.model_copy(deep=True)
        return EmotionalState(
            joy=_decay(state.joy, profile.joy_decay_per_time_unit, elapsed_time_units),
            anger=_decay(state.anger, profile.anger_decay_per_time_unit, elapsed_time_units),
            fear=_decay(state.fear, profile.fear_decay_per_time_unit, elapsed_time_units),
            sadness=_decay(state.sadness, profile.sadness_decay_per_time_unit, elapsed_time_units),
            curiosity=_decay(
                state.curiosity,
                profile.curiosity_decay_per_time_unit,
                elapsed_time_units,
            ),
            attraction=_decay(
                state.attraction,
                profile.attraction_decay_per_time_unit,
                elapsed_time_units,
            ),
            jealousy=_decay(
                state.jealousy,
                profile.jealousy_decay_per_time_unit,
                elapsed_time_units,
            ),
            shame=_decay(state.shame, profile.shame_decay_per_time_unit, elapsed_time_units),
            melancholy=_decay(
                state.melancholy,
                profile.melancholy_decay_per_time_unit,
                elapsed_time_units,
            ),
        )

    @staticmethod
    def _apply_emotion_effect(
        state: EmotionalState,
        effect: EmotionEffect,
        intensity: float,
        profile: PsychologyProfile,
    ) -> EmotionalState:
        return EmotionalState(
            joy=_clamp(
                state.joy + _scaled(effect.joy, intensity, profile.joy_sensitivity),
                0.0,
                10.0,
            ),
            anger=_clamp(
                state.anger + _scaled(effect.anger, intensity, profile.anger_sensitivity),
                0.0,
                10.0,
            ),
            fear=_clamp(
                state.fear + _scaled(effect.fear, intensity, profile.fear_sensitivity),
                0.0,
                10.0,
            ),
            sadness=_clamp(
                state.sadness + _scaled(effect.sadness, intensity, profile.sadness_sensitivity),
                0.0,
                10.0,
            ),
            curiosity=_clamp(
                state.curiosity
                + _scaled(effect.curiosity, intensity, profile.curiosity_sensitivity),
                0.0,
                10.0,
            ),
            attraction=_clamp(
                state.attraction
                + _scaled(effect.attraction, intensity, profile.emotion_attraction_sensitivity),
                0.0,
                10.0,
            ),
            jealousy=_clamp(
                state.jealousy + _scaled(effect.jealousy, intensity, profile.jealousy_sensitivity),
                0.0,
                10.0,
            ),
            shame=_clamp(
                state.shame + _scaled(effect.shame, intensity, profile.shame_sensitivity),
                0.0,
                10.0,
            ),
            melancholy=_clamp(
                state.melancholy
                + _scaled(effect.melancholy, intensity, profile.melancholy_sensitivity),
                0.0,
                10.0,
            ),
        )

    @staticmethod
    def _apply_relationship_effect(
        state: RelationshipState,
        effect: RelationshipEffect,
        intensity: float,
        profile: PsychologyProfile,
    ) -> RelationshipState:
        return RelationshipState(
            trust=_clamp(
                state.trust + _scaled(effect.trust, intensity, profile.trust_sensitivity),
                -10.0,
                10.0,
            ),
            fear=_clamp(
                state.fear
                + _scaled(effect.fear, intensity, profile.relationship_fear_sensitivity),
                -10.0,
                10.0,
            ),
            attraction=_clamp(
                state.attraction
                + _scaled(
                    effect.attraction,
                    intensity,
                    profile.relationship_attraction_sensitivity,
                ),
                -10.0,
                10.0,
            ),
            affection=_clamp(
                state.affection
                + _scaled(effect.affection, intensity, profile.affection_sensitivity),
                -10.0,
                10.0,
            ),
            resentment=_clamp(
                state.resentment
                + _scaled(effect.resentment, intensity, profile.resentment_sensitivity),
                -10.0,
                10.0,
            ),
            dependency=_clamp(
                state.dependency
                + _scaled(effect.dependency, intensity, profile.dependency_sensitivity),
                -10.0,
                10.0,
            ),
            respect=_clamp(
                state.respect + _scaled(effect.respect, intensity, profile.respect_sensitivity),
                -10.0,
                10.0,
            ),
            suspicion=_clamp(
                state.suspicion
                + _scaled(effect.suspicion, intensity, profile.suspicion_sensitivity),
                -10.0,
                10.0,
            ),
        )

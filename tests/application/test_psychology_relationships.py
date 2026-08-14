import pytest
from pydantic import ValidationError

from epos.application.psychology import (
    PsychologicalEvent,
    PsychologicalEventType,
    PsychologyProfile,
    PsychologyService,
)
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState


def test_semantic_event_cannot_smuggle_authoritative_deltas() -> None:
    with pytest.raises(ValidationError):
        PsychologicalEvent(
            event_type=PsychologicalEventType.INSULT,
            intensity=0.8,
            trust_delta=-10.0,
        )


def test_insult_uses_python_owned_deterministic_effects() -> None:
    service = PsychologyService.default()

    result = service.apply_event(
        event=PsychologicalEvent(event_type=PsychologicalEventType.INSULT, intensity=1.0),
        emotions=EmotionalState(),
        relationship=RelationshipState(),
        profile=PsychologyProfile(),
    )

    assert result.emotions.anger == 2.0
    assert result.relationship.resentment == 1.0
    assert result.relationship.respect == -1.0
    assert result.relationship.trust == 0.0


def test_psychological_updates_are_clamped_to_domain_bounds() -> None:
    service = PsychologyService.default()

    result = service.apply_event(
        event=PsychologicalEvent(event_type=PsychologicalEventType.INSULT, intensity=1.0),
        emotions=EmotionalState(anger=9.5),
        relationship=RelationshipState(resentment=9.8, respect=-9.5),
        profile=PsychologyProfile(),
    )

    assert result.emotions.anger == 10.0
    assert result.relationship.resentment == 10.0
    assert result.relationship.respect == -10.0


def test_profile_sensitivity_changes_magnitude_not_rule_authority() -> None:
    service = PsychologyService.default()
    profile = PsychologyProfile(anger_sensitivity=0.5, resentment_sensitivity=2.0)

    result = service.apply_event(
        event=PsychologicalEvent(event_type=PsychologicalEventType.INSULT, intensity=1.0),
        emotions=EmotionalState(),
        relationship=RelationshipState(),
        profile=profile,
    )

    assert result.emotions.anger == 1.0
    assert result.relationship.resentment == 2.0
    assert result.relationship.respect == -1.0


def test_relationship_dimensions_remain_independent() -> None:
    service = PsychologyService.default()

    result = service.apply_event(
        event=PsychologicalEvent(event_type=PsychologicalEventType.PROMISE_KEPT, intensity=1.0),
        emotions=EmotionalState(),
        relationship=RelationshipState(attraction=4.0),
        profile=PsychologyProfile(),
    )

    assert result.relationship.trust > 0.0
    assert result.relationship.respect > 0.0
    assert result.relationship.attraction == 4.0


def test_emotional_decay_uses_elapsed_world_time_deterministically() -> None:
    service = PsychologyService.default()
    profile = PsychologyProfile(anger_decay_per_time_unit=0.5, joy_decay_per_time_unit=0.25)
    state = EmotionalState(anger=5.0, joy=2.0)

    decayed = service.decay_emotions(state, elapsed_time_units=4.0, profile=profile)

    assert decayed.anger == 3.0
    assert decayed.joy == 1.0


def test_zero_elapsed_time_does_not_change_emotions() -> None:
    service = PsychologyService.default()
    state = EmotionalState(anger=5.0, joy=2.0)

    unchanged = service.decay_emotions(
        state,
        elapsed_time_units=0.0,
        profile=PsychologyProfile(),
    )

    assert unchanged == state

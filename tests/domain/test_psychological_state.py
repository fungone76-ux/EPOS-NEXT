import pytest
from pydantic import ValidationError

from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState


def test_emotional_state_enforces_zero_to_ten_bounds() -> None:
    EmotionalState(joy=0, anger=10)

    with pytest.raises(ValidationError):
        EmotionalState(joy=10.01)

    with pytest.raises(ValidationError):
        EmotionalState(fear=-0.01)


def test_relationship_state_enforces_bounded_dimensions() -> None:
    RelationshipState(trust=-10, affection=10)

    with pytest.raises(ValidationError):
        RelationshipState(trust=10.01)

    with pytest.raises(ValidationError):
        RelationshipState(resentment=-10.01)

"""Python-owned semantic-to-psychological rules."""

from epos.application.psychology.models import (
    EmotionEffect,
    PsychologicalEventType,
    PsychologyRule,
    RelationshipEffect,
)


def default_rule_for(event_type: PsychologicalEventType) -> PsychologyRule:
    """Return a fresh deterministic rule for one generic semantic event type."""

    match event_type:
        case PsychologicalEventType.INSULT:
            return PsychologyRule(
                emotions=EmotionEffect(anger=2.0),
                relationship=RelationshipEffect(resentment=1.0, respect=-1.0),
            )
        case PsychologicalEventType.PRAISE:
            return PsychologyRule(
                emotions=EmotionEffect(joy=1.0),
                relationship=RelationshipEffect(affection=0.5, respect=0.5),
            )
        case PsychologicalEventType.THREAT:
            return PsychologyRule(
                emotions=EmotionEffect(fear=2.0),
                relationship=RelationshipEffect(fear=1.5, suspicion=0.5),
            )
        case PsychologicalEventType.REASSURANCE:
            return PsychologyRule(
                emotions=EmotionEffect(fear=-1.5),
                relationship=RelationshipEffect(trust=0.5),
            )
        case PsychologicalEventType.KINDNESS:
            return PsychologyRule(
                emotions=EmotionEffect(joy=1.0),
                relationship=RelationshipEffect(trust=0.5, affection=1.0),
            )
        case PsychologicalEventType.BETRAYAL:
            return PsychologyRule(
                emotions=EmotionEffect(anger=2.0, sadness=2.0),
                relationship=RelationshipEffect(
                    trust=-3.0,
                    resentment=3.0,
                    respect=-1.5,
                    suspicion=2.0,
                ),
            )
        case PsychologicalEventType.PROMISE_KEPT:
            return PsychologyRule(
                emotions=EmotionEffect(joy=0.5),
                relationship=RelationshipEffect(trust=1.5, affection=0.5, respect=1.0),
            )
        case PsychologicalEventType.PROMISE_BROKEN:
            return PsychologyRule(
                emotions=EmotionEffect(anger=1.0, sadness=1.0),
                relationship=RelationshipEffect(
                    trust=-1.5,
                    resentment=1.0,
                    respect=-0.5,
                    suspicion=1.0,
                ),
            )
        case PsychologicalEventType.HUMILIATION:
            return PsychologyRule(
                emotions=EmotionEffect(anger=1.0, shame=2.0),
                relationship=RelationshipEffect(resentment=1.0, respect=-1.0),
            )
        case PsychologicalEventType.SUPPORT:
            return PsychologyRule(
                emotions=EmotionEffect(joy=0.5, fear=-0.5),
                relationship=RelationshipEffect(trust=0.75, affection=0.75),
            )
    raise AssertionError(f"unsupported psychological event type: {event_type}")

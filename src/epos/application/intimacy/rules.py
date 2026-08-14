"""Python-owned semantic rules for NPC intimacy state."""

from epos.application.intimacy.models import IntimacyEffect, IntimacyEventType


def default_effect_for(event_type: IntimacyEventType) -> IntimacyEffect:
    match event_type:
        case IntimacyEventType.FLIRT:
            return IntimacyEffect(sexual_attraction=0.6, desire=0.3, tension=0.6)
        case IntimacyEventType.MUTUAL_FLIRT:
            return IntimacyEffect(
                sexual_attraction=1.0,
                desire=0.8,
                arousal=0.5,
                tension=0.8,
            )
        case IntimacyEventType.INTIMATE_APPROACH:
            return IntimacyEffect(desire=0.4, arousal=0.6, tension=0.7)
        case IntimacyEventType.INTIMATE_ACCEPTED:
            return IntimacyEffect(desire=0.6, arousal=1.0, comfort=0.8, tension=0.5)
        case IntimacyEventType.INTIMATE_DECLINED:
            return IntimacyEffect(desire=-0.5, arousal=-0.8, tension=-0.4)
        case IntimacyEventType.AFTERCARE:
            return IntimacyEffect(arousal=-0.5, comfort=1.0, tension=-0.8)
    raise AssertionError(f"unsupported intimacy event type: {event_type}")

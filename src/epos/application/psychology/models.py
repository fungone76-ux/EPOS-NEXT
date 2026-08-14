"""Typed semantic contracts for deterministic psychology updates."""

from enum import StrEnum

from pydantic import Field

from epos.domain.base import DomainModel
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState


class PsychologicalEventType(StrEnum):
    INSULT = "insult"
    PRAISE = "praise"
    THREAT = "threat"
    REASSURANCE = "reassurance"
    KINDNESS = "kindness"
    BETRAYAL = "betrayal"
    PROMISE_KEPT = "promise_kept"
    PROMISE_BROKEN = "promise_broken"
    HUMILIATION = "humiliation"
    SUPPORT = "support"


class PsychologicalEvent(DomainModel):
    """Semantic event proposal. It intentionally contains no authoritative deltas."""

    event_type: PsychologicalEventType
    intensity: float = Field(ge=0.0, le=1.0)
    context_tags: tuple[str, ...] = ()


class PsychologyProfile(DomainModel):
    """Deterministic per-NPC tuning, separate from current emotional state."""

    joy_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    anger_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    fear_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    sadness_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    curiosity_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    emotion_attraction_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    jealousy_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    shame_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    melancholy_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)

    trust_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    relationship_fear_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    relationship_attraction_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    affection_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    resentment_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    dependency_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    respect_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    suspicion_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)

    joy_decay_per_time_unit: float = Field(default=0.0, ge=0.0)
    anger_decay_per_time_unit: float = Field(default=0.0, ge=0.0)
    fear_decay_per_time_unit: float = Field(default=0.0, ge=0.0)
    sadness_decay_per_time_unit: float = Field(default=0.0, ge=0.0)
    curiosity_decay_per_time_unit: float = Field(default=0.0, ge=0.0)
    attraction_decay_per_time_unit: float = Field(default=0.0, ge=0.0)
    jealousy_decay_per_time_unit: float = Field(default=0.0, ge=0.0)
    shame_decay_per_time_unit: float = Field(default=0.0, ge=0.0)
    melancholy_decay_per_time_unit: float = Field(default=0.0, ge=0.0)


class PsychologicalUpdate(DomainModel):
    emotions: EmotionalState
    relationship: RelationshipState


class EmotionEffect(DomainModel):
    joy: float = 0.0
    anger: float = 0.0
    fear: float = 0.0
    sadness: float = 0.0
    curiosity: float = 0.0
    attraction: float = 0.0
    jealousy: float = 0.0
    shame: float = 0.0
    melancholy: float = 0.0


class RelationshipEffect(DomainModel):
    trust: float = 0.0
    fear: float = 0.0
    attraction: float = 0.0
    affection: float = 0.0
    resentment: float = 0.0
    dependency: float = 0.0
    respect: float = 0.0
    suspicion: float = 0.0


class PsychologyRule(DomainModel):
    emotions: EmotionEffect = Field(default_factory=EmotionEffect)
    relationship: RelationshipEffect = Field(default_factory=RelationshipEffect)

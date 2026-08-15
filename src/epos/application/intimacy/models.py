"""Typed contracts for adult intimacy and scoped consent."""

from enum import StrEnum

from pydantic import Field, model_validator

from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, TurnNumber


class ConsentScope(StrEnum):
    KISS = "kiss"
    INTIMATE_CONTACT = "intimate_contact"
    SEXUAL_ACTIVITY = "sexual_activity"


class ConsentStatus(StrEnum):
    GRANTED = "granted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


class ConsentSignal(DomainModel):
    actor_id: EntityId
    partner_id: EntityId
    scope: ConsentScope
    status: ConsentStatus
    turn: TurnNumber


class IntimacyAuthorizationRequest(DomainModel):
    player_id: EntityId
    npc_id: EntityId
    scope: ConsentScope
    current_turn: TurnNumber
    player_adult_verified: bool
    npc_adult_verified: bool
    player_consent: ConsentSignal | None = None
    npc_consent: ConsentSignal | None = None


class IntimacyAuthorization(DomainModel):
    allowed: bool
    scope: ConsentScope
    turn: TurnNumber
    reasons: tuple[str, ...] = ()


class AuthorizedIntimacyVisual(DomainModel):
    """Adult visual semantic authorized by two scoped, current-turn signals."""

    authorization: IntimacyAuthorization
    player_id: EntityId
    npc_id: EntityId
    visual_intent: str = Field(min_length=1, max_length=180)
    visual_tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_authorized(self) -> "AuthorizedIntimacyVisual":
        if not self.authorization.allowed:
            raise ValueError("adult visual requires an allowed intimacy authorization")
        return self


class IntimacyTurnResolution(DomainModel):
    """Auditable result for one explicit player intimacy request."""

    authorization: IntimacyAuthorization
    visual: AuthorizedIntimacyVisual | None = None

    @model_validator(mode="after")
    def validate_visual_gate(self) -> "IntimacyTurnResolution":
        if self.authorization.allowed != (self.visual is not None):
            raise ValueError("authorized intimacy and adult visual must agree")
        if self.visual is not None and self.visual.authorization != self.authorization:
            raise ValueError("adult visual authorization does not match turn resolution")
        return self


class IntimacyEventType(StrEnum):
    FLIRT = "flirt"
    MUTUAL_FLIRT = "mutual_flirt"
    INTIMATE_APPROACH = "intimate_approach"
    INTIMATE_ACCEPTED = "intimate_accepted"
    INTIMATE_DECLINED = "intimate_declined"
    AFTERCARE = "aftercare"


class IntimacyEvent(DomainModel):
    """Semantic interpretation only; it carries no authoritative state deltas."""

    event_type: IntimacyEventType
    intensity: float = Field(ge=0.0, le=1.0)
    context_tags: tuple[str, ...] = ()


class IntimacyProfile(DomainModel):
    """Per-NPC sensitivities, separate from current intimacy state."""

    sexual_attraction_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    desire_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    arousal_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    comfort_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)
    tension_sensitivity: float = Field(default=1.0, ge=0.0, le=3.0)


class IntimacyEffect(DomainModel):
    sexual_attraction: float = 0.0
    desire: float = 0.0
    arousal: float = 0.0
    comfort: float = 0.0
    tension: float = 0.0

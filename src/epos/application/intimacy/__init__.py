"""Adult intimacy contracts and deterministic service."""

from epos.application.intimacy.models import (
    ConsentScope,
    ConsentSignal,
    ConsentStatus,
    IntimacyAuthorization,
    IntimacyAuthorizationRequest,
    IntimacyEvent,
    IntimacyEventType,
    IntimacyProfile,
)
from epos.application.intimacy.service import IntimacyService

__all__ = [
    "ConsentScope",
    "ConsentSignal",
    "ConsentStatus",
    "IntimacyAuthorization",
    "IntimacyAuthorizationRequest",
    "IntimacyEvent",
    "IntimacyEventType",
    "IntimacyProfile",
    "IntimacyService",
]

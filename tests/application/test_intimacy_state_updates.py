import pytest
from pydantic import ValidationError

from epos.application.intimacy import (
    ConsentScope,
    ConsentSignal,
    ConsentStatus,
    IntimacyAuthorizationRequest,
    IntimacyEvent,
    IntimacyEventType,
    IntimacyProfile,
    IntimacyService,
)
from epos.domain.errors import ContractError
from epos.domain.ids import EntityId, TurnNumber
from epos.domain.intimacy import IntimacyState


def test_semantic_intimacy_event_cannot_carry_authoritative_deltas() -> None:
    event = IntimacyEvent(event_type=IntimacyEventType.FLIRT, intensity=0.5)

    assert event.intensity == 0.5

    with pytest.raises(ValidationError):
        IntimacyEvent(
            event_type=IntimacyEventType.FLIRT,
            intensity=0.5,
            desire_delta=10.0,
        )


def test_python_rules_update_npc_intimacy_state_and_clamp_values() -> None:
    service = IntimacyService.default()
    state = IntimacyState(sexual_attraction=9.8, desire=9.8, tension=9.8)

    updated = service.apply_event(
        state=state,
        event=IntimacyEvent(event_type=IntimacyEventType.MUTUAL_FLIRT, intensity=1.0),
        profile=IntimacyProfile(),
    )

    assert updated.sexual_attraction == 10.0
    assert updated.desire == 10.0
    assert updated.tension == 10.0
    assert state.sexual_attraction == 9.8


def test_completed_sexual_activity_requires_authorization() -> None:
    service = IntimacyService.default()
    player_id = EntityId("player")
    npc_id = EntityId("victoria")
    turn = TurnNumber(20)
    state = IntimacyState(comfort=7.0)

    denied = service.authorize(
        IntimacyAuthorizationRequest(
            player_id=player_id,
            npc_id=npc_id,
            scope=ConsentScope.SEXUAL_ACTIVITY,
            current_turn=turn,
            player_adult_verified=True,
            npc_adult_verified=True,
        )
    )

    with pytest.raises(ContractError, match="not authorized"):
        service.record_completed_sexual_activity(
            state=state,
            authorization=denied,
            turn=turn,
        )

    player_grant = ConsentSignal(
        actor_id=player_id,
        partner_id=npc_id,
        scope=ConsentScope.SEXUAL_ACTIVITY,
        status=ConsentStatus.GRANTED,
        turn=turn,
    )
    npc_grant = ConsentSignal(
        actor_id=npc_id,
        partner_id=player_id,
        scope=ConsentScope.SEXUAL_ACTIVITY,
        status=ConsentStatus.GRANTED,
        turn=turn,
    )
    allowed = service.authorize(
        IntimacyAuthorizationRequest(
            player_id=player_id,
            npc_id=npc_id,
            scope=ConsentScope.SEXUAL_ACTIVITY,
            current_turn=turn,
            player_adult_verified=True,
            npc_adult_verified=True,
            player_consent=player_grant,
            npc_consent=npc_grant,
        )
    )

    updated = service.record_completed_sexual_activity(
        state=state,
        authorization=allowed,
        turn=turn,
    )

    assert updated.completed_sexual_encounters == 1
    assert updated.last_intimate_turn == turn
    assert state.completed_sexual_encounters == 0

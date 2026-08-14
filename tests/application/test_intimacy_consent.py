from epos.application.intimacy import (
    ConsentScope,
    ConsentSignal,
    ConsentStatus,
    IntimacyAuthorizationRequest,
    IntimacyService,
)


PLAYER_ID = "player"
NPC_ID = "victoria"
TURN = 12


def grant(actor_id: str, partner_id: str, scope: ConsentScope) -> ConsentSignal:
    return ConsentSignal(
        actor_id=actor_id,
        partner_id=partner_id,
        scope=scope,
        status=ConsentStatus.GRANTED,
        turn=TURN,
    )


def request(
    *,
    player_consent: ConsentSignal | None,
    npc_consent: ConsentSignal | None,
    player_adult_verified: bool = True,
    npc_adult_verified: bool = True,
) -> IntimacyAuthorizationRequest:
    return IntimacyAuthorizationRequest(
        player_id=PLAYER_ID,
        npc_id=NPC_ID,
        scope=ConsentScope.SEXUAL_ACTIVITY,
        current_turn=TURN,
        player_adult_verified=player_adult_verified,
        npc_adult_verified=npc_adult_verified,
        player_consent=player_consent,
        npc_consent=npc_consent,
    )


def test_authorization_never_infers_consent_from_intimacy_scores() -> None:
    service = IntimacyService.default()

    authorization = service.authorize(request(player_consent=None, npc_consent=None))

    assert "desire" not in IntimacyAuthorizationRequest.model_fields
    assert "arousal" not in IntimacyAuthorizationRequest.model_fields
    assert authorization.allowed is False
    assert "missing_player_consent" in authorization.reasons
    assert "missing_npc_consent" in authorization.reasons


def test_exact_current_turn_consent_from_both_participants_authorizes() -> None:
    service = IntimacyService.default()

    authorization = service.authorize(
        request(
            player_consent=grant(PLAYER_ID, NPC_ID, ConsentScope.SEXUAL_ACTIVITY),
            npc_consent=grant(NPC_ID, PLAYER_ID, ConsentScope.SEXUAL_ACTIVITY),
        )
    )

    assert authorization.allowed is True
    assert authorization.reasons == ()


def test_wrong_scope_withdrawal_or_non_adult_status_blocks_authorization() -> None:
    service = IntimacyService.default()
    wrong_scope = grant(PLAYER_ID, NPC_ID, ConsentScope.KISS)
    withdrawn = ConsentSignal(
        actor_id=NPC_ID,
        partner_id=PLAYER_ID,
        scope=ConsentScope.SEXUAL_ACTIVITY,
        status=ConsentStatus.WITHDRAWN,
        turn=TURN,
    )

    wrong_scope_result = service.authorize(
        request(
            player_consent=wrong_scope,
            npc_consent=grant(NPC_ID, PLAYER_ID, ConsentScope.SEXUAL_ACTIVITY),
        )
    )
    withdrawn_result = service.authorize(
        request(
            player_consent=grant(PLAYER_ID, NPC_ID, ConsentScope.SEXUAL_ACTIVITY),
            npc_consent=withdrawn,
        )
    )
    adult_gate_result = service.authorize(
        request(
            player_consent=grant(PLAYER_ID, NPC_ID, ConsentScope.SEXUAL_ACTIVITY),
            npc_consent=grant(NPC_ID, PLAYER_ID, ConsentScope.SEXUAL_ACTIVITY),
            npc_adult_verified=False,
        )
    )

    assert wrong_scope_result.allowed is False
    assert withdrawn_result.allowed is False
    assert adult_gate_result.allowed is False

"""Bridge explicit player intent and NPC response into an adult visual gate."""

from epos.application.actions.models import ValidatedAction
from epos.application.cognition.models import CognitionResult
from epos.application.intimacy.models import (
    AuthorizedIntimacyVisual,
    ConsentSignal,
    ConsentStatus,
    IntimacyAuthorizationRequest,
    IntimacyTurnResolution,
)
from epos.application.intimacy.service import IntimacyService
from epos.domain.ids import TurnNumber
from epos.domain.world_state import WorldState


class PythonTurnIntimacyResolver:
    """Never infer consent: bind the two explicit signals and authorize in Python."""

    def __init__(self, service: IntimacyService | None = None) -> None:
        self._service = service or IntimacyService.default()

    def resolve(
        self,
        *,
        state: WorldState,
        action: ValidatedAction,
        reactions: tuple[CognitionResult, ...],
        turn: TurnNumber,
    ) -> IntimacyTurnResolution | None:
        request = action.intimacy_request
        if request is None:
            return None

        player_id = state.player.entity_id
        npc = state.npcs.get(request.target_id)
        npc_response = next(
            (
                result.reaction.intimacy_response
                for result in reactions
                if result.reaction.npc_id == request.target_id
            ),
            None,
        )
        player_consent = ConsentSignal(
            actor_id=player_id,
            partner_id=request.target_id,
            scope=request.scope,
            status=ConsentStatus.GRANTED,
            turn=turn,
        )
        npc_consent = (
            None
            if npc_response is None
            else ConsentSignal(
                actor_id=request.target_id,
                partner_id=player_id,
                scope=npc_response.scope,
                status=npc_response.status,
                turn=turn,
            )
        )
        authorization = self._service.authorize(
            IntimacyAuthorizationRequest(
                player_id=player_id,
                npc_id=request.target_id,
                scope=request.scope,
                current_turn=turn,
                player_adult_verified=state.player.adult_verified,
                npc_adult_verified=npc is not None and npc.adult_verified,
                player_consent=player_consent,
                npc_consent=npc_consent,
            )
        )
        visual = (
            AuthorizedIntimacyVisual(
                authorization=authorization,
                player_id=player_id,
                npc_id=request.target_id,
                visual_intent=request.visual_intent,
                visual_tags=tuple(
                    dict.fromkeys((request.scope.value, *request.visual_tags))
                ),
            )
            if authorization.allowed
            else None
        )
        return IntimacyTurnResolution(authorization=authorization, visual=visual)

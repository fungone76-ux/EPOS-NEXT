"""Exact-dice checkpoint creation and resume validation."""

from __future__ import annotations

import hashlib
import json

from epos.application.actions.models import CheckProposal, ResolvedCheck, ValidatedAction
from epos.application.state.errors import CheckpointStateMismatchError
from epos.application.state.models import DiceCheckpoint, StateReference
from epos.application.state.ports import DiceCheckpointStorePort
from epos.domain.world_state import WorldState


def state_fingerprint(state: WorldState) -> str:
    payload = json.dumps(
        state.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class DiceCheckpointService:
    def __init__(self, *, store: DiceCheckpointStorePort) -> None:
        self._store = store

    async def save_after_roll(
        self,
        *,
        state: WorldState,
        player_input: str,
        validated_action: ValidatedAction,
        proposal: CheckProposal,
        resolved_check: ResolvedCheck,
        player_decision: str,
    ) -> DiceCheckpoint:
        checkpoint = DiceCheckpoint(
            session_id=state.session_id,
            state_reference=StateReference(
                session_id=state.session_id,
                turn_number=state.turn_number,
                fingerprint=state_fingerprint(state),
            ),
            player_input=player_input,
            validated_action=validated_action.model_copy(deep=True),
            proposal=proposal.model_copy(deep=True),
            resolved_check=resolved_check.model_copy(deep=True),
            player_decision=player_decision,
        )
        await self._store.save(checkpoint)
        return checkpoint.model_copy(deep=True)

    async def resume(self, *, state: WorldState) -> DiceCheckpoint | None:
        checkpoint = await self._store.load(state.session_id)
        if checkpoint is None:
            return None

        expected = StateReference(
            session_id=state.session_id,
            turn_number=state.turn_number,
            fingerprint=state_fingerprint(state),
        )
        if checkpoint.state_reference != expected:
            raise CheckpointStateMismatchError(
                "checkpoint state reference does not match authoritative state"
            )
        return checkpoint.model_copy(deep=True)

    async def clear(self, *, state: WorldState) -> None:
        await self._store.delete(state.session_id)

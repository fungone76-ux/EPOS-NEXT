"""Authoritative validate-copy-apply-validate-persist-swap commit service."""

from __future__ import annotations

import asyncio
from copy import deepcopy

from epos.application.ports import StateStorePort
from epos.application.state.models import MutationBatch
from epos.application.state.mutations import apply_mutation
from epos.application.state.validation import (
    MutationAuthorityValidator,
    WorldStateCommitValidator,
)
from epos.domain.world_state import WorldState


class AuthoritativeStateManager:
    """Own the live state and swap it only after persistence succeeds."""

    def __init__(
        self,
        *,
        initial_state: WorldState,
        state_store: StateStorePort[WorldState],
    ) -> None:
        self._state = initial_state.model_copy(deep=True)
        self._state_store = state_store
        self._lock = asyncio.Lock()

    def snapshot(self) -> WorldState:
        return self._state.model_copy(deep=True)

    async def commit(self, batch: MutationBatch) -> WorldState:
        async with self._lock:
            MutationAuthorityValidator.validate(batch)
            candidate = deepcopy(self._state)
            for mutation in batch.mutations:
                apply_mutation(candidate, mutation)

            validated = WorldStateCommitValidator.validate(candidate)
            await self._state_store.save(validated.session_id, validated)
            self._state = validated
            return self._state.model_copy(deep=True)

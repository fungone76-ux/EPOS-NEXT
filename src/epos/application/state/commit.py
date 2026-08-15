"""Authoritative validate-copy-apply-validate-persist-swap commit service."""

from __future__ import annotations

import asyncio
from copy import deepcopy

from epos.application.ports import StateStorePort
from epos.application.state.errors import StaleAuthoritativeStateError
from epos.application.state.models import MutationBatch
from epos.application.state.mutations import apply_mutation
from epos.application.state.validation import (
    MutationAuthorityValidator,
    WorldStateCommitValidator,
)
from epos.domain.errors import EposError, PersistenceError
from epos.domain.world_state import WorldState


def _project(base_state: WorldState, batches: tuple[MutationBatch, ...]) -> WorldState:
    candidate = deepcopy(base_state)
    for batch in batches:
        MutationAuthorityValidator.validate(batch)
        for mutation in batch.mutations:
            apply_mutation(candidate, mutation)
    return WorldStateCommitValidator.validate(candidate)


class AuthoritativeStateManager:
    """Own the live state and swap it only after persistence is confirmed."""

    def __init__(
        self,
        *,
        initial_state: WorldState,
        state_store: StateStorePort[WorldState],
    ) -> None:
        self._state = WorldStateCommitValidator.validate(
            initial_state.model_copy(deep=True)
        )
        self._state_store = state_store
        self._lock = asyncio.Lock()

    def snapshot(self) -> WorldState:
        return self._state.model_copy(deep=True)

    async def commit(self, batch: MutationBatch) -> WorldState:
        return await self.commit_many((batch,))

    async def commit_many(
        self,
        batches: tuple[MutationBatch, ...],
        *,
        expected_state: WorldState | None = None,
    ) -> WorldState:
        """Apply heterogeneous authority batches in one atomic state transaction."""

        async with self._lock:
            if expected_state is not None and self._state != expected_state:
                raise StaleAuthoritativeStateError(
                    "authoritative state changed while turn was planned"
                )
            validated = _project(self._state, batches)
            await self._persist_or_reconcile(validated)
            self._state = validated
            return self._state.model_copy(deep=True)

    def project_many(
        self,
        batches: tuple[MutationBatch, ...],
        *,
        base_state: WorldState | None = None,
    ) -> WorldState:
        """Validate and project turn effects without persisting or swapping live state."""

        base = self._state if base_state is None else WorldStateCommitValidator.validate(base_state)
        return _project(base, batches)

    async def _persist_or_reconcile(self, validated: WorldState) -> None:
        try:
            await self._state_store.save(validated.session_id, validated)
            return
        except PersistenceError as save_error:
            try:
                persisted = await self._state_store.load(validated.session_id)
            except EposError as reconciliation_error:
                raise save_error from reconciliation_error
            if persisted != validated:
                raise save_error

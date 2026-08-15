from __future__ import annotations

import pytest

from epos.application.state import (
    MutationAuthority,
    MutationAuthorityError,
    MutationBatch,
    ReplaceNPCBondStateMutation,
)
from epos.application.state.validation import MutationAuthorityValidator
from epos.domain.bond import BondPhase, BondState
from epos.domain.ids import EntityId


def test_llm_proposable_batch_cannot_set_bond_state() -> None:
    batch = MutationBatch(
        producer=MutationAuthority.LLM_PROPOSABLE,
        mutations=(
            ReplaceNPCBondStateMutation(
                npc_id=EntityId("victoria"),
                bond_state=BondState(phase=BondPhase.DEEP),
            ),
        ),
    )

    with pytest.raises(MutationAuthorityError, match="requires engine_only"):
        MutationAuthorityValidator.validate(batch)

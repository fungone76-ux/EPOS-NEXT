from __future__ import annotations

from pathlib import Path

import pytest

from epos.application.actions.models import CheckOutcome, CheckProposal, ResolvedCheck
from epos.application.state import DiceCheckpoint, StateReference
from epos.domain.ids import SessionId, SkillId
from epos.infrastructure.persistence.json_checkpoint import JsonFileCheckpointStore


@pytest.mark.asyncio
async def test_json_checkpoint_store_round_trips_exact_dice_and_can_clear(tmp_path: Path) -> None:
    store = JsonFileCheckpointStore(root=tmp_path)
    checkpoint = DiceCheckpoint(
        session_id=SessionId("session-1"),
        state_reference=StateReference(
            session_id=SessionId("session-1"),
            turn_number=8,
            fingerprint="a" * 64,
        ),
        proposal=CheckProposal(skill_id=SkillId("negoziazione"), difficulty=4),
        resolved_check=ResolvedCheck(
            skill_id=SkillId("negoziazione"),
            difficulty=4,
            rating=3,
            pool_size=3,
            dice=(1, 4, 3),
            success_count=1,
            outcome=CheckOutcome.PARTIAL_SUCCESS,
        ),
        player_decision="proceed",
    )

    await store.save(checkpoint)
    restored = await store.load(checkpoint.session_id)

    assert restored == checkpoint
    assert restored is not None
    assert restored.resolved_check.dice == (1, 4, 3)

    await store.delete(checkpoint.session_id)

    assert await store.load(checkpoint.session_id) is None

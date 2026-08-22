from epos.application.conversation.models import (
    NarrationAuditFinding,
    NarrationAuditProposal,
    NarrationViolationKind,
)
from epos.application.conversation.narration import NarrationService


def test_only_unsupported_npc_fact_findings_are_soft_after_repair() -> None:
    audit = NarrationAuditProposal(
        findings=(
            NarrationAuditFinding(
                kind=NarrationViolationKind.UNSUPPORTED_NPC_FACT,
                unit_index=0,
            ),
        )
    )

    assert NarrationService._only_soft_npc_fact_findings(audit)


def test_mixed_or_hard_findings_remain_blocking() -> None:
    mixed = NarrationAuditProposal(
        findings=(
            NarrationAuditFinding(
                kind=NarrationViolationKind.UNSUPPORTED_NPC_FACT,
                unit_index=0,
            ),
            NarrationAuditFinding(
                kind=NarrationViolationKind.PLAYER_CONTROL,
                unit_index=0,
            ),
        )
    )
    hard = NarrationAuditProposal(
        findings=(
            NarrationAuditFinding(
                kind=NarrationViolationKind.UNSUPPORTED_WORLD_CLAIM,
                unit_index=0,
            ),
        )
    )
    clean = NarrationAuditProposal()

    assert not NarrationService._only_soft_npc_fact_findings(mixed)
    assert not NarrationService._only_soft_npc_fact_findings(hard)
    assert not NarrationService._only_soft_npc_fact_findings(clean)

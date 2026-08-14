"""Semantic narration audit: LLM classifies, Python rejects violations."""

from __future__ import annotations

from epos.application.conversation.models import (
    NarrationAuditProposal,
    ValidatedNarration,
)
from epos.application.conversation.validation import NarrationValidationError


class NarrationAuditValidator:
    """Validate audit references and reject every reported semantic violation."""

    def validate(
        self,
        audit: NarrationAuditProposal,
        candidate: ValidatedNarration,
    ) -> None:
        unit_count = len(candidate.units)
        for finding in audit.findings:
            if finding.unit_index >= unit_count:
                raise NarrationValidationError(
                    f"narration audit references invalid unit {finding.unit_index}"
                )

        if audit.findings:
            kinds = ",".join(finding.kind.value for finding in audit.findings)
            raise NarrationValidationError(f"narration semantic audit rejected: {kinds}")

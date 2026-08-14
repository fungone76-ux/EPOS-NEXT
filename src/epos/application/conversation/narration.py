"""Narration LLM use case plus semantic audit and deterministic composition."""

from __future__ import annotations

from epos.application.conversation.audit import NarrationAuditValidator
from epos.application.conversation.models import (
    NarrationAuditContext,
    NarrationAuditProposal,
    NarrationContext,
    NarrationProposal,
    NarrationResult,
    NPCDialogueDraft,
    ValidatedNarration,
)
from epos.application.conversation.validation import NarrationValidator
from epos.application.ports import LLMPort


class NarrationComposer:
    """Deterministically format validated units without inventing new content."""

    def compose(self, narration: ValidatedNarration, context: NarrationContext) -> str:
        names = {voice.npc_id: voice.name for voice in context.voices}
        lines: list[str] = []
        for unit in narration.units:
            if isinstance(unit, NPCDialogueDraft):
                name = names[unit.speaker_id]
                lines.append(f"{name}: {unit.text}")
            else:
                lines.append(unit.text)
        return "\n".join(lines)


class NarrationService:
    """Generate, structurally validate, semantically audit, then expose narration."""

    def __init__(
        self,
        *,
        port: LLMPort[NarrationContext, NarrationProposal],
        audit_port: LLMPort[NarrationAuditContext, NarrationAuditProposal],
        validator: NarrationValidator,
        audit_validator: NarrationAuditValidator,
        composer: NarrationComposer | None = None,
    ) -> None:
        self._port = port
        self._audit_port = audit_port
        self._validator = validator
        self._audit_validator = audit_validator
        self._composer = composer or NarrationComposer()

    async def generate(self, context: NarrationContext) -> NarrationResult:
        proposal = await self._port.invoke(context)
        validated = self._validator.validate(proposal, context)
        audit_context = NarrationAuditContext(
            narration_context=context.model_copy(deep=True),
            candidate=validated.model_copy(deep=True),
        )
        audit = await self._audit_port.invoke(audit_context)
        self._audit_validator.validate(audit, validated)
        text = self._composer.compose(validated, context)
        return NarrationResult(
            focus=context.focus.model_copy(deep=True),
            units=validated.units,
            text=text,
        )

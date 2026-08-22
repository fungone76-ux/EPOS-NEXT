"""Narration LLM use case plus semantic audit and deterministic composition."""

from __future__ import annotations

from epos.application.conversation.audit import NarrationAuditValidator
from epos.application.conversation.models import (
    NarrationAuditContext,
    NarrationAuditProposal,
    NarrationContext,
    NarrationMode,
    NarrationProposal,
    NarrationRepairFeedback,
    NarrationResult,
    NarrationViolationKind,
    NPCDialogueDraft,
    ValidatedNarration,
    WorldNarrationDraft,
)
from epos.application.conversation.validation import (
    NarrationValidationError,
    NarrationValidator,
)
from epos.application.ports import LLMPort

_MAX_NARRATION_ATTEMPTS = 2
_FOCUSED_MODES = frozenset(
    {
        NarrationMode.BRIEF_SOCIAL,
        NarrationMode.DIRECT_DIALOGUE,
        NarrationMode.FOCUSED_INTERACTION,
    }
)


class NarrationOrderCanonicalizer:
    """Apply deterministic focus priority without discarding valid LLM prose."""

    def canonicalize(
        self,
        proposal: NarrationProposal,
        context: NarrationContext,
    ) -> NarrationProposal:
        target = context.focus.target_npc_id
        if context.focus.mode not in _FOCUSED_MODES or target is None:
            return proposal

        target_index = next(
            (
                index
                for index, unit in enumerate(proposal.units)
                if isinstance(unit, NPCDialogueDraft) and unit.speaker_id == target
            ),
            None,
        )
        if target_index is None or target_index == 0:
            return proposal

        target_unit = proposal.units[target_index]
        remaining = (
            *proposal.units[:target_index],
            *proposal.units[target_index + 1 :],
        )
        return proposal.model_copy(update={"units": (target_unit, *remaining)}, deep=True)


class ObservationNarrationFallback:
    """Create a minimal narration from canonical observation data only."""

    def build(self, context: NarrationContext) -> NarrationProposal | None:
        observation = context.scene.resolved_action.action.observation
        if observation is None:
            return None
        if "action:resolved" not in {item.evidence_id for item in context.evidence}:
            return None
        subject = next(
            (
                item
                for item in context.scene.visible_subjects
                if item.entity_id == observation.subject_id
            ),
            None,
        )
        if subject is None:
            return None
        return NarrationProposal(
            units=(
                WorldNarrationDraft(
                    text=f"Osservi attentamente {subject.name}.",
                    evidence_ids=("action:resolved",),
                    subject_ids=(subject.entity_id,),
                ),
            )
        )


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
        order_canonicalizer: NarrationOrderCanonicalizer | None = None,
        observation_fallback: ObservationNarrationFallback | None = None,
    ) -> None:
        self._port = port
        self._audit_port = audit_port
        self._validator = validator
        self._audit_validator = audit_validator
        self._composer = composer or NarrationComposer()
        self._order_canonicalizer = order_canonicalizer or NarrationOrderCanonicalizer()
        self._observation_fallback = observation_fallback or ObservationNarrationFallback()

    async def generate(self, context: NarrationContext) -> NarrationResult:
        attempt_context = context
        last_error: NarrationValidationError | None = None
        for attempt in range(_MAX_NARRATION_ATTEMPTS):
            audit: NarrationAuditProposal | None = None
            proposal = await self._port.invoke(attempt_context)
            proposal = self._order_canonicalizer.canonicalize(proposal, context)
            try:
                validated = self._validator.validate(proposal, context)
                audit_context = NarrationAuditContext(
                    narration_context=context.model_copy(deep=True),
                    candidate=validated.model_copy(deep=True),
                )
                audit = await self._audit_port.invoke(audit_context)
                if (
                    attempt + 1 == _MAX_NARRATION_ATTEMPTS
                    and self._only_soft_npc_fact_findings(audit)
                ):
                    return self._result(validated, context)
                self._audit_validator.validate(audit, validated)
            except NarrationValidationError as exc:
                last_error = exc
                if attempt + 1 < _MAX_NARRATION_ATTEMPTS:
                    issues = (
                        tuple(
                            f"unit {finding.unit_index}: {finding.kind.value}"
                            for finding in audit.findings
                        )
                        if audit is not None and audit.findings
                        else (str(exc),)
                    )
                    attempt_context = context.model_copy(
                        update={
                            "repair_feedback": NarrationRepairFeedback(
                                rejected_candidate_json=proposal.model_dump_json(),
                                issues=issues,
                            )
                        },
                        deep=True,
                    )
                    continue
                return self._fallback_or_raise(context, exc)
            return self._result(validated, context)

        if last_error is None:
            raise RuntimeError("narration recovery exhausted without a result")
        return self._fallback_or_raise(context, last_error)

    @staticmethod
    def _only_soft_npc_fact_findings(audit: NarrationAuditProposal) -> bool:
        return bool(audit.findings) and all(
            finding.kind is NarrationViolationKind.UNSUPPORTED_NPC_FACT
            for finding in audit.findings
        )

    def _fallback_or_raise(
        self,
        context: NarrationContext,
        error: NarrationValidationError,
    ) -> NarrationResult:
        proposal = self._observation_fallback.build(context)
        if proposal is None:
            raise error
        validated = self._validator.validate(proposal, context)
        return self._result(validated, context)

    def _result(
        self,
        validated: ValidatedNarration,
        context: NarrationContext,
    ) -> NarrationResult:
        text = self._composer.compose(validated, context)
        return NarrationResult(
            focus=context.focus.model_copy(deep=True),
            units=validated.units,
            text=text,
        )

"""Narration LLM use case plus deterministic player-facing composition."""

from __future__ import annotations

from epos.application.conversation.models import (
    NPCDialogueDraft,
    NarrationContext,
    NarrationProposal,
    NarrationResult,
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
    """Generate natural language from safe context, then validate before exposing it."""

    def __init__(
        self,
        *,
        port: LLMPort[NarrationContext, NarrationProposal],
        validator: NarrationValidator,
        composer: NarrationComposer | None = None,
    ) -> None:
        self._port = port
        self._validator = validator
        self._composer = composer or NarrationComposer()

    async def generate(self, context: NarrationContext) -> NarrationResult:
        proposal = await self._port.invoke(context)
        validated = self._validator.validate(proposal, context)
        text = self._composer.compose(validated, context)
        return NarrationResult(
            focus=context.focus.model_copy(deep=True),
            units=validated.units,
            text=text,
        )

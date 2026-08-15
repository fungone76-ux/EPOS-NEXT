"""Semantic conversation-focus classification and Python validation."""

from __future__ import annotations

from epos.application.conversation.models import (
    ConversationFocus,
    ConversationFocusContext,
    ConversationFocusProposal,
    NarrationMode,
)
from epos.application.conversation.validation import ConversationFocusValidationError
from epos.application.ports import LLMPort

_CONVERSATIONAL_MODES = frozenset(
    {
        NarrationMode.BRIEF_SOCIAL,
        NarrationMode.DIRECT_DIALOGUE,
        NarrationMode.FOCUSED_INTERACTION,
    }
)


class ConversationFocusValidator:
    """Keep the player as speaker and preserve explicitly addressed NPC focus."""

    def validate(
        self,
        proposal: ConversationFocusProposal,
        context: ConversationFocusContext,
    ) -> ConversationFocus:
        if proposal.speaker_id != context.player_id:
            raise ConversationFocusValidationError("conversation speaker must be the player")

        present = set(context.present_npc_ids)
        target = proposal.target_npc_id
        addressed_npcs = tuple(
            target_id for target_id in context.action.target_ids if target_id in present
        )
        if target is None and addressed_npcs:
            target = addressed_npcs[0]

        mode = (
            NarrationMode.EXPLORATION
            if context.action.observation is not None
            else proposal.mode
        )
        if target is None and mode in _CONVERSATIONAL_MODES:
            mode = (
                NarrationMode.BRIEF_SOCIAL
                if context.present_npc_ids
                else NarrationMode.ACTION
            )

        if target is not None and target not in present:
            raise ConversationFocusValidationError(f"conversation target {target} is not present")

        if mode in {
            NarrationMode.DIRECT_DIALOGUE,
            NarrationMode.FOCUSED_INTERACTION,
        } and target is None:
            raise ConversationFocusValidationError(
                f"narration mode {mode} requires a target NPC"
            )

        if addressed_npcs and target not in addressed_npcs:
            raise ConversationFocusValidationError(
                "conversation target conflicts with the NPC addressed by the player action"
            )

        return ConversationFocus(
            speaker_id=proposal.speaker_id,
            target_npc_id=target,
            topic=proposal.topic,
            mode=mode,
        )


class ConversationFocusService:
    """Use semantic LLM classification; Python validates the resulting focus."""

    def __init__(
        self,
        *,
        port: LLMPort[ConversationFocusContext, ConversationFocusProposal],
        validator: ConversationFocusValidator,
    ) -> None:
        self._port = port
        self._validator = validator

    async def classify(self, context: ConversationFocusContext) -> ConversationFocus:
        proposal = await self._port.invoke(context)
        return self._validator.validate(proposal, context)

"""Python authority checks for conversation focus and generated narration."""

from __future__ import annotations

import re

from epos.application.cognition.models import ValidatedNPCReaction
from epos.application.conversation.models import (
    NarrationContext,
    NarrationEvidence,
    NarrationEvidenceKind,
    NarrationMode,
    NarrationProposal,
    NPCDialogueDraft,
    ValidatedNarration,
    WorldNarrationDraft,
)
from epos.application.visual.models import SubjectKind
from epos.domain.errors import EposValidationError
from epos.domain.ids import EntityId

_SENTENCE_END = re.compile(r"[.!?]+(?:[\"'»”)]*)")

_PRIVATE_EVIDENCE = frozenset(
    {
        NarrationEvidenceKind.NPC_REACTION,
        NarrationEvidenceKind.NPC_KNOWLEDGE,
        NarrationEvidenceKind.NPC_BELIEF,
        NarrationEvidenceKind.NPC_FALSE_BELIEF,
        NarrationEvidenceKind.NPC_DISCOVERY,
        NarrationEvidenceKind.NPC_MEMORY,
        NarrationEvidenceKind.AUTHORIZED_SECRET,
    }
)
_PLAYER_GROUNDING = frozenset(
    {
        NarrationEvidenceKind.PLAYER_DECLARATION,
        NarrationEvidenceKind.ACTION_RESULT,
        NarrationEvidenceKind.CHECK_RESULT,
    }
)
_FOCUSED_MODES = frozenset(
    {
        NarrationMode.BRIEF_SOCIAL,
        NarrationMode.DIRECT_DIALOGUE,
        NarrationMode.FOCUSED_INTERACTION,
    }
)


class ConversationFocusValidationError(EposValidationError):
    def __init__(self, message: str, *, code: str = "conversation.focus.invalid") -> None:
        super().__init__(message, code=code)


class NarrationValidationError(EposValidationError):
    def __init__(self, message: str, *, code: str = "narration.proposal.invalid") -> None:
        super().__init__(message, code=code)


class NarrationValidator:
    """Validate focus priority, evidence ownership, and player-agency structure."""

    def validate(
        self,
        proposal: NarrationProposal,
        context: NarrationContext,
    ) -> ValidatedNarration:
        if not proposal.units:
            raise NarrationValidationError(
                "narration proposal must contain at least one unit"
            )

        evidence = {item.evidence_id: item for item in context.evidence}
        reactions = {reaction.npc_id: reaction for reaction in context.reactions}
        voice_ids = {voice.npc_id for voice in context.voices}
        present_ids = {subject.entity_id for subject in context.scene.visible_subjects}
        present_npc_ids = {
            subject.entity_id
            for subject in context.scene.visible_subjects
            if subject.kind is SubjectKind.NPC
        }

        self._validate_focus_priority(proposal, context)
        for unit in proposal.units:
            if isinstance(unit, NPCDialogueDraft):
                self._validate_dialogue(
                    unit,
                    evidence=evidence,
                    reactions=reactions,
                    voice_ids=voice_ids,
                    present_npc_ids=present_npc_ids,
                )
            else:
                self._validate_world_narration(
                    unit,
                    evidence=evidence,
                    context=context,
                    present_ids=present_ids,
                )

        if context.focus.mode is NarrationMode.BRIEF_SOCIAL:
            self._validate_brief_social(proposal, context)

        return ValidatedNarration(
            units=tuple(unit.model_copy(deep=True) for unit in proposal.units)
        )

    @staticmethod
    def _validate_focus_priority(
        proposal: NarrationProposal,
        context: NarrationContext,
    ) -> None:
        if context.focus.mode not in _FOCUSED_MODES:
            return
        target = context.focus.target_npc_id
        if target is None:
            raise NarrationValidationError("focused narration has no target NPC")
        first = proposal.units[0]
        if not isinstance(first, NPCDialogueDraft):
            raise NarrationValidationError(
                "target NPC response must be the first narration unit"
            )
        if first.speaker_id != target:
            raise NarrationValidationError(
                f"conversation focus requires target NPC {target} to respond first"
            )

    @staticmethod
    def _validate_dialogue(
        unit: NPCDialogueDraft,
        *,
        evidence: dict[str, NarrationEvidence],
        reactions: dict[EntityId, ValidatedNPCReaction],
        voice_ids: set[EntityId],
        present_npc_ids: set[EntityId],
    ) -> None:
        if unit.speaker_id not in present_npc_ids:
            raise NarrationValidationError(
                f"dialogue speaker {unit.speaker_id} is not a present NPC"
            )
        if unit.speaker_id not in reactions or unit.speaker_id not in voice_ids:
            raise NarrationValidationError(
                f"dialogue speaker {unit.speaker_id} has no authorized NPC reaction"
            )
        if not unit.evidence_ids:
            raise NarrationValidationError("NPC dialogue must cite authorized evidence")

        required_reaction_id = f"reaction:{unit.speaker_id}"
        if required_reaction_id not in unit.evidence_ids:
            raise NarrationValidationError(
                f"NPC dialogue must cite its authorized reaction {required_reaction_id}"
            )

        for evidence_id in unit.evidence_ids:
            item = NarrationValidator._evidence(evidence, evidence_id)
            if item.owner_id is not None and item.owner_id != unit.speaker_id:
                raise NarrationValidationError(
                    f"private evidence owner {item.owner_id} does not match "
                    f"speaker {unit.speaker_id}"
                )

    @staticmethod
    def _validate_world_narration(
        unit: WorldNarrationDraft,
        *,
        evidence: dict[str, NarrationEvidence],
        context: NarrationContext,
        present_ids: set[EntityId],
    ) -> None:
        if not unit.evidence_ids:
            raise NarrationValidationError(
                "world narration must cite authorized evidence"
            )
        cited = tuple(
            NarrationValidator._evidence(evidence, item)
            for item in unit.evidence_ids
        )
        if any(item.kind in _PRIVATE_EVIDENCE for item in cited):
            raise NarrationValidationError(
                "world narration cannot promote private NPC evidence to world fact"
            )
        for subject_id in unit.subject_ids:
            if subject_id not in present_ids:
                raise NarrationValidationError(
                    f"narration subject {subject_id} is not present"
                )
        if context.player_id in unit.subject_ids and not any(
            item.kind in _PLAYER_GROUNDING for item in cited
        ):
            raise NarrationValidationError(
                "player narration requires grounding in the player's declaration or resolved result"
            )

    @staticmethod
    def _validate_brief_social(
        proposal: NarrationProposal,
        context: NarrationContext,
    ) -> None:
        target = context.focus.target_npc_id
        for unit in proposal.units:
            if isinstance(unit, NPCDialogueDraft) and unit.speaker_id != target:
                raise NarrationValidationError(
                    "brief_social conversation focus forbids unrelated NPC initiative"
                )
        sentence_count = sum(
            NarrationValidator._sentence_count(unit.text)
            for unit in proposal.units
        )
        if sentence_count < 1 or sentence_count > 2:
            raise NarrationValidationError(
                "brief_social narration must normally remain within one or two sentences"
            )

    @staticmethod
    def _sentence_count(text: str) -> int:
        count = len(_SENTENCE_END.findall(text))
        return count if count > 0 else 1

    @staticmethod
    def _evidence(
        evidence: dict[str, NarrationEvidence],
        evidence_id: str,
    ) -> NarrationEvidence:
        item = evidence.get(evidence_id)
        if item is None:
            raise NarrationValidationError(
                f"unknown narration evidence {evidence_id}"
            )
        return item

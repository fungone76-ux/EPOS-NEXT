from __future__ import annotations

import pytest

from epos.application.actions.models import ValidatedAction
from epos.application.cognition.models import CognitionScene, ValidatedNPCReaction
from epos.application.conversation.audit import NarrationAuditValidator
from epos.application.conversation.models import (
    ConversationFocus,
    NarrationAuditContext,
    NarrationAuditFinding,
    NarrationAuditProposal,
    NarrationContext,
    NarrationEvidence,
    NarrationEvidenceKind,
    NarrationMode,
    NarrationProposal,
    NarrationViolationKind,
    NPCDialogueDraft,
    NPCNarrationVoice,
    ValidatedNarration,
    WorldNarrationDraft,
)
from epos.application.conversation.narration import NarrationService
from epos.application.conversation.validation import NarrationValidationError, NarrationValidator
from epos.domain.ids import EntityId, LocationId
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState


def _context() -> NarrationContext:
    player = EntityId("player")
    victoria = EntityId("victoria")
    return NarrationContext(
        player_id=player,
        player_input="Buona sera Victoria!",
        focus=ConversationFocus(
            speaker_id=player,
            target_npc_id=victoria,
            topic="greeting",
            mode=NarrationMode.DIRECT_DIALOGUE,
        ),
        scene=CognitionScene(
            location_id=LocationId("lobby"),
            present_entity_ids=(player, victoria),
            summary="Il player saluta Victoria nella hall.",
        ),
        action=ValidatedAction(intent="dialogue", target_ids=(victoria,)),
        reactions=(
            ValidatedNPCReaction(
                npc_id=victoria,
                intent="respond_to_greeting",
                speech_act="acknowledge",
                topic_tags=("greeting",),
                target_ids=(player,),
            ),
        ),
        voices=(
            NPCNarrationVoice(
                npc_id=victoria,
                name="Victoria",
                emotional_state=EmotionalState(),
                relationship_with_player=RelationshipState(),
            ),
        ),
        evidence=(
            NarrationEvidence(
                evidence_id="reaction:victoria",
                kind=NarrationEvidenceKind.NPC_REACTION,
                owner_id=victoria,
                text="intent=respond_to_greeting; speech_act=acknowledge; topics=greeting",
            ),
            NarrationEvidence(
                evidence_id="player:declared_input",
                kind=NarrationEvidenceKind.PLAYER_DECLARATION,
                owner_id=player,
                text="Buona sera Victoria!",
            ),
        ),
    )


class PlayerControlNarrator:
    async def invoke(self, request: NarrationContext) -> NarrationProposal:
        return NarrationProposal(
            units=(
                NPCDialogueDraft(
                    speaker_id=EntityId("victoria"),
                    text="Buona sera.",
                    evidence_ids=("reaction:victoria",),
                ),
                WorldNarrationDraft(
                    text="Il player decide di seguirla.",
                    evidence_ids=("player:declared_input",),
                    subject_ids=(request.player_id,),
                ),
            )
        )


class PlayerControlAuditPort:
    async def invoke(self, request: NarrationAuditContext) -> NarrationAuditProposal:
        assert request.candidate.units[1].text == "Il player decide di seguirla."
        return NarrationAuditProposal(
            findings=(
                NarrationAuditFinding(
                    kind=NarrationViolationKind.PLAYER_CONTROL,
                    unit_index=1,
                ),
            )
        )


class CleanNarrator:
    async def invoke(self, request: NarrationContext) -> NarrationProposal:
        del request
        return NarrationProposal(
            units=(
                NPCDialogueDraft(
                    speaker_id=EntityId("victoria"),
                    text="Buona sera.",
                    evidence_ids=("reaction:victoria",),
                ),
            )
        )


class CleanAuditPort:
    async def invoke(self, request: NarrationAuditContext) -> NarrationAuditProposal:
        assert isinstance(request.candidate, ValidatedNarration)
        return NarrationAuditProposal()


@pytest.mark.asyncio
async def test_semantic_audit_blocks_invented_player_decision() -> None:
    service = NarrationService(
        port=PlayerControlNarrator(),
        audit_port=PlayerControlAuditPort(),
        validator=NarrationValidator(),
        audit_validator=NarrationAuditValidator(),
    )

    with pytest.raises(NarrationValidationError, match="player_control"):
        await service.generate(_context())


@pytest.mark.asyncio
async def test_clean_semantic_audit_allows_validated_narration() -> None:
    service = NarrationService(
        port=CleanNarrator(),
        audit_port=CleanAuditPort(),
        validator=NarrationValidator(),
        audit_validator=NarrationAuditValidator(),
    )

    result = await service.generate(_context())

    assert result.text == "Victoria: Buona sera."


def test_audit_validator_rejects_out_of_range_unit_reference() -> None:
    candidate = ValidatedNarration(
        units=(
            NPCDialogueDraft(
                speaker_id=EntityId("victoria"),
                text="Buona sera.",
                evidence_ids=("reaction:victoria",),
            ),
        )
    )
    audit = NarrationAuditProposal(
        findings=(
            NarrationAuditFinding(
                kind=NarrationViolationKind.UNSUPPORTED_WORLD_CLAIM,
                unit_index=4,
            ),
        )
    )

    with pytest.raises(NarrationValidationError, match="unit"):
        NarrationAuditValidator().validate(audit, candidate)

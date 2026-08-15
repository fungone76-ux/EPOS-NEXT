from __future__ import annotations

import pytest

from epos.application.actions.models import ObservationIntent, ValidatedAction
from epos.application.cognition.models import ValidatedNPCReaction
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
from epos.application.visual import (
    ObservableSceneState,
    ObservableSubject,
    ResolvedSceneAction,
    SceneLocation,
    SceneTime,
    SubjectKind,
)
from epos.domain.ids import EntityId, LocationId, SceneId, SessionId, TurnNumber, WorldpackId
from epos.domain.outfit import OutfitState
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState
from epos.domain.visual_state import VisualState


def _scene() -> ObservableSceneState:
    player = EntityId("player")
    victoria = EntityId("victoria")
    return ObservableSceneState(
        scene_id=SceneId("session:1"),
        session_id=SessionId("session"),
        worldpack_id=WorldpackId("test_world"),
        location=SceneLocation(location_id=LocationId("lobby"), name="Lobby"),
        time=SceneTime(
            turn_number=TurnNumber(1),
            day=1,
            world_phase="evening",
        ),
        visible_subjects=(
            ObservableSubject(
                entity_id=player,
                kind=SubjectKind.PLAYER,
                name="Player",
                role="player",
                outfit=OutfitState(),
                visual_state=VisualState(),
            ),
            ObservableSubject(
                entity_id=victoria,
                kind=SubjectKind.NPC,
                name="Victoria",
                role="host",
                outfit=OutfitState(),
                visual_state=VisualState(),
            ),
        ),
        resolved_action=ResolvedSceneAction(
            action=ValidatedAction(
                intent="dialogue",
                target_ids=(victoria,),
            )
        ),
    )


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
        scene=_scene(),
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
                text=(
                    "intent=respond_to_greeting; speech_act=acknowledge; "
                    "topics=greeting"
                ),
            ),
            NarrationEvidence(
                evidence_id="player:declared_input",
                kind=NarrationEvidenceKind.PLAYER_DECLARATION,
                owner_id=player,
                text="Buona sera Victoria!",
            ),
        ),
    )


def _observation_context() -> NarrationContext:
    context = _context()
    player = context.player_id
    victoria = EntityId("victoria")
    action = ValidatedAction(
        intent="observe",
        target_ids=(victoria,),
        observation=ObservationIntent(subject_id=victoria, region="feet"),
    )
    scene = context.scene.model_copy(
        update={"resolved_action": ResolvedSceneAction(action=action)}
    )
    return context.model_copy(
        update={
            "player_input": "Guardo i piedi nudi di Victoria",
            "focus": ConversationFocus(
                speaker_id=player,
                target_npc_id=victoria,
                topic="bare_feet",
                mode=NarrationMode.EXPLORATION,
            ),
            "scene": scene,
            "evidence": (
                *context.evidence,
                NarrationEvidence(
                    evidence_id="action:resolved",
                    kind=NarrationEvidenceKind.ACTION_RESULT,
                    text=action.model_dump_json(),
                ),
            ),
        }
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
    async def invoke(
        self,
        request: NarrationAuditContext,
    ) -> NarrationAuditProposal:
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
    async def invoke(
        self,
        request: NarrationAuditContext,
    ) -> NarrationAuditProposal:
        assert isinstance(request.candidate, ValidatedNarration)
        return NarrationAuditProposal()


class RepairingObservationNarrator:
    def __init__(self) -> None:
        self.calls = 0

    async def invoke(self, request: NarrationContext) -> NarrationProposal:
        self.calls += 1
        if self.calls == 1:
            assert request.repair_feedback is None
            text = "I piedi di Victoria brillano di una luce soprannaturale."
        else:
            assert request.repair_feedback is not None
            assert "unsupported_world_claim" in request.repair_feedback.issues[0]
            text = "Rivolgi lo sguardo verso Victoria."
        return NarrationProposal(
            units=(
                WorldNarrationDraft(
                    text=text,
                    evidence_ids=("action:resolved",),
                    subject_ids=(EntityId("victoria"),),
                ),
            )
        )


class RepairThenCleanAuditPort:
    def __init__(self) -> None:
        self.calls = 0

    async def invoke(
        self,
        request: NarrationAuditContext,
    ) -> NarrationAuditProposal:
        self.calls += 1
        if self.calls == 1:
            return NarrationAuditProposal(
                findings=(
                    NarrationAuditFinding(
                        kind=NarrationViolationKind.UNSUPPORTED_WORLD_CLAIM,
                        unit_index=0,
                    ),
                )
            )
        assert request.candidate.units[0].text == "Rivolgi lo sguardo verso Victoria."
        return NarrationAuditProposal()


class AlwaysRejectedObservationNarrator:
    async def invoke(self, request: NarrationContext) -> NarrationProposal:
        del request
        return NarrationProposal(
            units=(
                WorldNarrationDraft(
                    text="Una luce soprannaturale avvolge Victoria.",
                    evidence_ids=("action:resolved",),
                    subject_ids=(EntityId("victoria"),),
                ),
            )
        )


class AlwaysRejectingAuditPort:
    async def invoke(
        self,
        request: NarrationAuditContext,
    ) -> NarrationAuditProposal:
        del request
        return NarrationAuditProposal(
            findings=(
                NarrationAuditFinding(
                    kind=NarrationViolationKind.UNSUPPORTED_WORLD_CLAIM,
                    unit_index=0,
                ),
            )
        )


class ReversedFocusedNarrator:
    async def invoke(self, request: NarrationContext) -> NarrationProposal:
        return NarrationProposal(
            units=(
                WorldNarrationDraft(
                    text="Le tue parole risuonano nella hall.",
                    evidence_ids=("player:declared_input",),
                    subject_ids=(request.player_id,),
                ),
                NPCDialogueDraft(
                    speaker_id=EntityId("victoria"),
                    text="Benvenuto.",
                    evidence_ids=("reaction:victoria",),
                ),
            )
        )


class TargetFirstAuditPort:
    async def invoke(
        self,
        request: NarrationAuditContext,
    ) -> NarrationAuditProposal:
        first = request.candidate.units[0]
        assert isinstance(first, NPCDialogueDraft)
        assert first.speaker_id == EntityId("victoria")
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


@pytest.mark.asyncio
async def test_semantic_audit_rejection_repairs_narration_before_failing_turn() -> None:
    narrator = RepairingObservationNarrator()
    audit = RepairThenCleanAuditPort()
    service = NarrationService(
        port=narrator,
        audit_port=audit,
        validator=NarrationValidator(),
        audit_validator=NarrationAuditValidator(),
    )

    result = await service.generate(_observation_context())

    assert result.text == "Rivolgi lo sguardo verso Victoria."
    assert narrator.calls == 2
    assert audit.calls == 2


@pytest.mark.asyncio
async def test_repeated_observation_audit_failure_uses_safe_fallback() -> None:
    service = NarrationService(
        port=AlwaysRejectedObservationNarrator(),
        audit_port=AlwaysRejectingAuditPort(),
        validator=NarrationValidator(),
        audit_validator=NarrationAuditValidator(),
    )

    result = await service.generate(_observation_context())

    assert result.text == "Osservi attentamente Victoria."
    assert result.units[0].evidence_ids == ("action:resolved",)


@pytest.mark.asyncio
async def test_focused_narration_is_reordered_instead_of_failing_turn() -> None:
    service = NarrationService(
        port=ReversedFocusedNarrator(),
        audit_port=TargetFirstAuditPort(),
        validator=NarrationValidator(),
        audit_validator=NarrationAuditValidator(),
    )

    result = await service.generate(_context())

    assert result.text == (
        "Victoria: Benvenuto.\nLe tue parole risuonano nella hall."
    )


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

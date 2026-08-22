from __future__ import annotations

import pytest

from epos.application.actions.models import ValidatedAction
from epos.application.cognition.models import ValidatedNPCReaction
from epos.application.conversation.audit import NarrationAuditValidator
from epos.application.conversation.models import (
    ConversationFocus,
    NarrationAuditContext,
    NarrationAuditProposal,
    NarrationContext,
    NarrationEvidence,
    NarrationEvidenceKind,
    NarrationMode,
    NarrationProposal,
    NPCDialogueDraft,
    NPCNarrationVoice,
)
from epos.application.conversation.narration import NarrationService
from epos.application.conversation.validation import NarrationValidator
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


class AlwaysTooLongBriefSocialNarrator:
    def __init__(self) -> None:
        self.calls = 0

    async def invoke(self, request: NarrationContext) -> NarrationProposal:
        self.calls += 1
        if self.calls == 1:
            assert request.repair_feedback is None
        else:
            assert request.repair_feedback is not None
        return NarrationProposal(
            units=(
                NPCDialogueDraft(
                    speaker_id=EntityId("victoria"),
                    text="Ciao. È un piacere vederti. Dimmi pure cosa ti porta qui.",
                    evidence_ids=("reaction:victoria",),
                ),
            )
        )


class AuditMustNotRun:
    async def invoke(self, request: NarrationAuditContext) -> NarrationAuditProposal:
        del request
        raise AssertionError("structurally invalid brief social narration must not reach audit")


def _context() -> NarrationContext:
    player = EntityId("player")
    victoria = EntityId("victoria")
    action = ValidatedAction(intent="greet", target_ids=(victoria,))
    scene = ObservableSceneState(
        scene_id=SceneId("session:1"),
        session_id=SessionId("session"),
        worldpack_id=WorldpackId("test_world"),
        location=SceneLocation(location_id=LocationId("lobby"), name="Lobby"),
        time=SceneTime(turn_number=TurnNumber(1), day=1, world_phase="evening"),
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
        resolved_action=ResolvedSceneAction(action=action),
    )
    reaction = ValidatedNPCReaction(
        npc_id=victoria,
        intent="respond_to_greeting",
        speech_act="acknowledge",
        topic_tags=("greeting",),
        target_ids=(player,),
    )
    return NarrationContext(
        player_id=player,
        player_input="Ciao Victoria.",
        focus=ConversationFocus(
            speaker_id=player,
            target_npc_id=victoria,
            topic="greeting",
            mode=NarrationMode.BRIEF_SOCIAL,
        ),
        scene=scene,
        reactions=(reaction,),
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
                text="Ciao Victoria.",
            ),
        ),
    )


@pytest.mark.asyncio
async def test_brief_social_uses_short_fallback_after_two_overlong_candidates() -> None:
    narrator = AlwaysTooLongBriefSocialNarrator()
    service = NarrationService(
        port=narrator,
        audit_port=AuditMustNotRun(),
        validator=NarrationValidator(),
        audit_validator=NarrationAuditValidator(),
    )

    result = await service.generate(_context())

    assert narrator.calls == 2
    assert result.text == "Victoria: Ciao."
    assert len(result.units) == 1
    assert result.units[0].evidence_ids == ("reaction:victoria",)

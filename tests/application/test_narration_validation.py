from __future__ import annotations

import pytest
from pydantic import ValidationError

from epos.application.actions.models import ValidatedAction
from epos.application.cognition.models import ValidatedNPCReaction
from epos.application.conversation.models import (
    ConversationFocus,
    NarrationContext,
    NarrationEvidence,
    NarrationEvidenceKind,
    NarrationMode,
    NarrationProposal,
    NPCDialogueDraft,
    NPCNarrationVoice,
    WorldNarrationDraft,
)
from epos.application.conversation.validation import NarrationValidationError, NarrationValidator
from epos.application.visual import (
    ObservableConsequence,
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
    player_id = EntityId("player")
    victoria_id = EntityId("victoria")
    stella_id = EntityId("stella")
    return ObservableSceneState(
        scene_id=SceneId("session:40"),
        session_id=SessionId("session"),
        worldpack_id=WorldpackId("resort_world"),
        location=SceneLocation(location_id=LocationId("lobby"), name="Lobby"),
        time=SceneTime(
            turn_number=TurnNumber(40),
            day=3,
            world_phase="evening",
        ),
        visible_subjects=(
            ObservableSubject(
                entity_id=player_id,
                kind=SubjectKind.PLAYER,
                name="Alex",
                role="player",
                outfit=OutfitState(),
                visual_state=VisualState(),
            ),
            ObservableSubject(
                entity_id=victoria_id,
                kind=SubjectKind.NPC,
                name="Victoria",
                role="host",
                outfit=OutfitState(),
                visual_state=VisualState(),
            ),
            ObservableSubject(
                entity_id=stella_id,
                kind=SubjectKind.NPC,
                name="Stella",
                role="guest",
                outfit=OutfitState(),
                visual_state=VisualState(),
            ),
        ),
        resolved_action=ResolvedSceneAction(
            action=ValidatedAction(
                intent="dialogue",
                target_ids=(victoria_id,),
            )
        ),
        observable_consequences=(
            ObservableConsequence(
                consequence_id="lobby_quiet",
                kind="environment",
                fact="La hall resta silenziosa.",
            ),
        ),
    )


def _context(mode: NarrationMode = NarrationMode.BRIEF_SOCIAL) -> NarrationContext:
    player_id = EntityId("player")
    victoria_id = EntityId("victoria")
    stella_id = EntityId("stella")
    return NarrationContext(
        player_id=player_id,
        player_input="Buona sera Victoria!",
        focus=ConversationFocus(
            speaker_id=player_id,
            target_npc_id=victoria_id,
            topic="greeting",
            mode=mode,
        ),
        scene=_scene(),
        reactions=(
            ValidatedNPCReaction(
                npc_id=victoria_id,
                intent="respond_to_greeting",
                speech_act="acknowledge",
                topic_tags=("greeting",),
                target_ids=(player_id,),
            ),
            ValidatedNPCReaction(
                npc_id=stella_id,
                intent="comment",
                speech_act="comment",
                topic_tags=("greeting",),
                target_ids=(player_id,),
            ),
        ),
        voices=(
            NPCNarrationVoice(
                npc_id=victoria_id,
                name="Victoria",
                personality=("controlled",),
                speech_style="precise",
                emotional_state=EmotionalState(),
                relationship_with_player=RelationshipState(),
            ),
            NPCNarrationVoice(
                npc_id=stella_id,
                name="Stella",
                emotional_state=EmotionalState(),
                relationship_with_player=RelationshipState(),
            ),
        ),
        evidence=(
            NarrationEvidence(
                evidence_id="reaction:victoria",
                kind=NarrationEvidenceKind.NPC_REACTION,
                owner_id=victoria_id,
                text="respond_to_greeting acknowledge greeting",
            ),
            NarrationEvidence(
                evidence_id="reaction:stella",
                kind=NarrationEvidenceKind.NPC_REACTION,
                owner_id=stella_id,
                text="comment greeting",
            ),
            NarrationEvidence(
                evidence_id="scene:consequence:lobby_quiet",
                kind=NarrationEvidenceKind.OBSERVABLE,
                text="La hall resta silenziosa.",
            ),
            NarrationEvidence(
                evidence_id="npc:victoria:knowledge:luna",
                kind=NarrationEvidenceKind.NPC_KNOWLEDGE,
                owner_id=victoria_id,
                text="Luna dirige il resort.",
            ),
        ),
    )


def _victoria_line(text: str = "Buona sera.") -> NPCDialogueDraft:
    return NPCDialogueDraft(
        speaker_id=EntityId("victoria"),
        text=text,
        evidence_ids=("reaction:victoria",),
    )


def test_brief_social_accepts_one_or_two_sentences_from_target_npc() -> None:
    proposal = NarrationProposal(
        units=(_victoria_line("Buona sera. È un piacere rivederti."),)
    )

    validated = NarrationValidator().validate(proposal, _context())

    assert validated.units[0].speaker_id == EntityId("victoria")


def test_open_brief_social_accepts_a_present_authorized_npc_response() -> None:
    context = _context().model_copy(
        update={
            "focus": ConversationFocus(
                speaker_id=EntityId("player"),
                target_npc_id=None,
                topic="introduction",
                mode=NarrationMode.BRIEF_SOCIAL,
            )
        }
    )
    proposal = NarrationProposal(units=(_victoria_line("Benvenuto, Andrea."),))

    validated = NarrationValidator().validate(proposal, context)

    assert validated.units[0].speaker_id == EntityId("victoria")


def test_brief_social_rejects_unrelated_npc_initiative() -> None:
    proposal = NarrationProposal(
        units=(
            NPCDialogueDraft(
                speaker_id=EntityId("stella"),
                text="Intervengo io.",
                evidence_ids=("reaction:stella",),
            ),
            _victoria_line(),
        )
    )

    with pytest.raises(NarrationValidationError, match="focus"):
        NarrationValidator().validate(proposal, _context())


def test_brief_social_rejects_more_than_two_sentences() -> None:
    proposal = NarrationProposal(
        units=(
            _victoria_line(
                "Buona sera. Come stai? Ho molte cose da raccontarti."
            ),
        )
    )

    with pytest.raises(NarrationValidationError, match="brief_social"):
        NarrationValidator().validate(proposal, _context())


def test_direct_dialogue_requires_target_npc_response_before_world_narration() -> None:
    proposal = NarrationProposal(
        units=(
            WorldNarrationDraft(
                text="La hall resta silenziosa.",
                evidence_ids=("scene:consequence:lobby_quiet",),
            ),
            _victoria_line(),
        )
    )

    with pytest.raises(NarrationValidationError, match="first"):
        NarrationValidator().validate(
            proposal,
            _context(NarrationMode.DIRECT_DIALOGUE),
        )


def test_world_narration_cannot_promote_private_npc_knowledge_to_world_fact() -> None:
    proposal = NarrationProposal(
        units=(
            WorldNarrationDraft(
                text="Luna dirige il resort.",
                evidence_ids=("npc:victoria:knowledge:luna",),
            ),
        )
    )

    with pytest.raises(NarrationValidationError, match="private"):
        NarrationValidator().validate(
            proposal,
            _context(NarrationMode.EXPLORATION),
        )


def test_npc_dialogue_cannot_use_another_npc_private_evidence() -> None:
    proposal = NarrationProposal(
        units=(
            NPCDialogueDraft(
                speaker_id=EntityId("stella"),
                text="So cosa pensa Victoria.",
                evidence_ids=(
                    "npc:victoria:knowledge:luna",
                    "reaction:stella",
                ),
            ),
        )
    )

    with pytest.raises(NarrationValidationError, match="owner"):
        NarrationValidator().validate(
            proposal,
            _context(NarrationMode.DRAMATIC_SCENE),
        )


def test_contract_has_no_player_dialogue_unit() -> None:
    with pytest.raises(ValidationError):
        NarrationProposal.model_validate(
            {
                "units": [
                    {
                        "kind": "player_dialogue",
                        "speaker_id": "player",
                        "text": "Accetto.",
                        "evidence_ids": ["scene:consequence:lobby_quiet"],
                    }
                ]
            }
        )

from __future__ import annotations

from pathlib import Path

import pytest

from epos.application.actions import (
    ActionInterpretation,
    ActionInterpreterContext,
    ActionValidator,
    IntimacyRequestProposal,
    ValidatedAction,
    ValidatedIntimacyRequest,
)
from epos.application.cognition import (
    CognitionResult,
    CognitionScene,
    CognitionValidationError,
    NPCIntimacyResponse,
    NPCReactionProposal,
    NPCReactionValidator,
    PrivateCognitiveContextBuilder,
    ValidatedNPCReaction,
)
from epos.application.intimacy import ConsentScope, ConsentStatus
from epos.application.intimacy.turn import PythonTurnIntimacyResolver
from epos.application.memory import MemoryRecallResult
from epos.application.visual import ObservableSceneBuilder, SceneObservationInput
from epos.application.visual.canonical import VisualCanonicalizer
from epos.application.visual.prompt import (
    PromptCompilerProfile,
    SemanticPromptCompiler,
    WorldpackVisualConfig,
)
from epos.application.visual.vst import (
    RawVST,
    SafetySignal,
    SemanticIntent,
    VSTActionIntent,
    VSTCameraIntent,
    VSTLightingIntent,
    VSTLocationIntent,
    VSTSafetyIntent,
    VSTStyleIntent,
    VSTSubjectIntent,
    VSTSubjectProminence,
    VSTVisualFocus,
)
from epos.domain.ids import EntityId, TurnNumber
from epos.domain.intimacy import IntimacyState
from epos.infrastructure.worldpacks import FileSystemWorldpackLoader

ROOT = Path(__file__).resolve().parents[2]
PLAYER = EntityId("player")
LUNA = EntityId("luna")


def _action() -> ValidatedAction:
    return ValidatedAction(
        intent="intimacy_request",
        target_ids=(LUNA,),
        intimacy_request=ValidatedIntimacyRequest(
            target_id=LUNA,
            scope=ConsentScope.KISS,
            visual_intent="passionate kiss",
            visual_tags=("kiss", "passionate"),
        ),
    )


def _reaction(status: ConsentStatus) -> CognitionResult:
    return CognitionResult(
        reaction=ValidatedNPCReaction(
            npc_id=LUNA,
            intent="answer_intimacy_request",
            speech_act="answer",
            target_ids=(PLAYER,),
            intimacy_response=NPCIntimacyResponse(
                scope=ConsentScope.KISS,
                status=status,
            ),
        )
    )


@pytest.mark.asyncio
async def test_resort_granted_consent_resolves_sex_library_into_prompt() -> None:
    loaded = await FileSystemWorldpackLoader().load(
        ROOT / "worldpacks" / "resort_world",
        session_id="adult-visual-bridge",
    )
    turn = TurnNumber(1)
    action = _action()
    resolution = PythonTurnIntimacyResolver().resolve(
        state=loaded.world_state,
        action=action,
        reactions=(_reaction(ConsentStatus.GRANTED),),
        turn=turn,
    )

    assert resolution is not None
    assert resolution.authorization.allowed is True
    assert resolution.visual is not None

    state = loaded.world_state.model_copy(update={"turn_number": turn}, deep=True)
    scene = ObservableSceneBuilder().build(
        state=state,
        observation=SceneObservationInput(
            action=action,
            authorized_intimacy_visual=resolution.visual,
        ),
    )
    raw = RawVST(
        scene_id=scene.scene_id,
        location=VSTLocationIntent(location_id=scene.location.location_id),
        subjects=(
            VSTSubjectIntent(
                entity_id=PLAYER,
                prominence=VSTSubjectProminence.SECONDARY,
            ),
            VSTSubjectIntent(
                entity_id=LUNA,
                prominence=VSTSubjectProminence.PRIMARY,
            ),
        ),
        action=VSTActionIntent(
            participants=(PLAYER, LUNA),
            intent=SemanticIntent(description="walking_forward"),
            shared=True,
        ),
        visual_focus=VSTVisualFocus(
            subject_ids=(LUNA,),
            intent=SemanticIntent(description="Luna is the primary subject"),
        ),
        camera=VSTCameraIntent(shot=SemanticIntent(description="extreme_wide_shot")),
        lighting=VSTLightingIntent(
            intent=SemanticIntent(description="bright_daylight")
        ),
        style=VSTStyleIntent(intent=SemanticIntent(description="cinematic_realism")),
        safety=VSTSafetyIntent(signal=SafetySignal.INTIMATE_CONTEXT),
    )

    canonical = VisualCanonicalizer().canonicalize(
        scene=scene,
        raw_vst=raw,
        worldpack=loaded,
    )
    prompt = SemanticPromptCompiler().compile(
        canonical,
        WorldpackVisualConfig.from_loaded_worldpack(
            loaded,
            profile=PromptCompilerProfile(),
        ),
    )

    assert canonical.adult_action is not None
    assert canonical.adult_action.entry_id == "kissing_intimate"
    assert "intimate deep kissing" in prompt.positive_prompt


@pytest.mark.asyncio
async def test_resort_high_desire_does_not_override_declined_consent() -> None:
    loaded = await FileSystemWorldpackLoader().load(
        ROOT / "worldpacks" / "resort_world",
        session_id="adult-visual-declined",
    )
    luna = loaded.world_state.npcs[LUNA]
    state = loaded.world_state.model_copy(deep=True)
    state.npcs[LUNA] = luna.model_copy(
        update={
            "intimacy": {
                PLAYER: IntimacyState(
                    sexual_attraction=10.0,
                    desire=10.0,
                    arousal=10.0,
                    comfort=10.0,
                )
            }
        },
        deep=True,
    )

    resolution = PythonTurnIntimacyResolver().resolve(
        state=state,
        action=_action(),
        reactions=(_reaction(ConsentStatus.DECLINED),),
        turn=TurnNumber(1),
    )

    assert resolution is not None
    assert resolution.authorization.allowed is False
    assert "npc_consent_not_granted" in resolution.authorization.reasons
    assert resolution.visual is None


@pytest.mark.asyncio
async def test_resort_missing_npc_answer_never_activates_adult_visual() -> None:
    loaded = await FileSystemWorldpackLoader().load(
        ROOT / "worldpacks" / "resort_world",
        session_id="adult-visual-no-answer",
    )

    resolution = PythonTurnIntimacyResolver().resolve(
        state=loaded.world_state,
        action=_action(),
        reactions=(),
        turn=TurnNumber(1),
    )

    assert resolution is not None
    assert resolution.authorization.allowed is False
    assert "missing_npc_consent" in resolution.authorization.reasons
    assert resolution.visual is None


@pytest.mark.asyncio
async def test_player_intent_and_npc_consent_are_validated_separately() -> None:
    loaded = await FileSystemWorldpackLoader().load(
        ROOT / "worldpacks" / "resort_world",
        session_id="adult-separate-signals",
    )
    interpretation = ActionInterpretation(
        intent="intimacy_request",
        target_ids=(LUNA,),
        intimacy_request=IntimacyRequestProposal(
            target_id=LUNA,
            scope=ConsentScope.KISS,
            visual_intent="passionate kiss",
            visual_tags=("kiss", "passionate"),
        ),
    )
    action_context = ActionInterpreterContext.from_world_state(
        loaded.world_state,
        player_input="Chiedo a Luna un bacio appassionato",
        known_location_ids=tuple(loaded.world_state.locations),
    )
    validated = ActionValidator().validate(interpretation, action_context)
    assert validated.intimacy_request is not None

    cognition_scene = CognitionScene(
        location_id=loaded.world_state.player.location_id,
        present_entity_ids=(PLAYER, *tuple(loaded.world_state.npcs)),
        summary="resort lobby",
    )
    private_context = PrivateCognitiveContextBuilder().build(
        state=loaded.world_state,
        npc_id=LUNA,
        scene=cognition_scene,
        player_input="Chiedo a Luna un bacio appassionato",
        action=validated,
        recalled=MemoryRecallResult(query_text="", memories=()),
        resolved_check=None,
    )

    with pytest.raises(
        CognitionValidationError,
        match="must explicitly answer intimacy request",
    ):
        NPCReactionValidator().validate(
            NPCReactionProposal(
                npc_id=LUNA,
                intent="answer_intimacy_request",
                speech_act="answer",
                target_ids=(PLAYER,),
            ),
            private_context,
        )

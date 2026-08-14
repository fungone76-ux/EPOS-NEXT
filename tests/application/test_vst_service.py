from __future__ import annotations

from typing import Protocol

import pytest

from epos.application.actions.models import ValidatedAction
from epos.application.visual import (
    ObservableSceneBuilder,
    SceneObservationInput,
    SceneSubjectCue,
)
from epos.application.visual.vst import (
    RawVST,
    SafetySignal,
    SemanticIntent,
    VisualDirectorContext,
    VisualDirectorContextBuilder,
    VisualDirectorService,
    VSTActionIntent,
    VSTCameraIntent,
    VSTLightingIntent,
    VSTLocationIntent,
    VSTSafetyIntent,
    VSTStyleIntent,
    VSTSubjectIntent,
    VSTSubjectProminence,
    VSTValidationError,
    VSTVisualFocus,
)
from epos.domain.ids import EntityId, LocationId, SceneId, SessionId, WorldpackId
from epos.domain.knowledge import KnowledgeState
from epos.domain.npc import NPCIdentity, NPCState, SecretState
from epos.domain.outfit import OutfitItem, OutfitState
from epos.domain.player import PlayerState
from epos.domain.psychology import EmotionalState
from epos.domain.visual_state import VisualState
from epos.domain.world_state import LocationState, WorldState


class VisualPortProtocol(Protocol):
    async def invoke(self, request: VisualDirectorContext) -> RawVST: ...


def _outfit(item_id: str, name: str, color: str) -> OutfitState:
    return OutfitState(
        items=(
            OutfitItem(
                item_id=item_id,
                name=name,
                slot="body",
                layer=0,
                coverage=("torso",),
                color=color,
            ),
        )
    )


def _world() -> WorldState:
    return WorldState(
        session_id=SessionId("session-visual"),
        worldpack_id=WorldpackId("resort-world"),
        turn_number=12,
        day=3,
        world_phase="sunset",
        player=PlayerState(
            entity_id=EntityId("player"),
            name="Player",
            location_id=LocationId("pool"),
            outfit=_outfit("shirt", "linen shirt", "blue"),
            visual_state=VisualState(traits={"wet_hair": True}),
        ),
        npcs={
            EntityId("victoria"): NPCState(
                identity=NPCIdentity(
                    entity_id=EntityId("victoria"),
                    name="Victoria",
                    role="resort_director",
                ),
                location_id=LocationId("pool"),
                outfit=_outfit("dress", "summer dress", "white"),
                visual_state=VisualState(traits={"wet_clothes": False}),
                emotional_state=EmotionalState(anger=8, attraction=5),
                knowledge=KnowledgeState(facts={"office_code": "4172"}),
                secrets=(
                    SecretState(
                        secret_id="letter",
                        fact="The letter is inside the office safe.",
                    ),
                ),
            ),
            EntityId("theron"): NPCState(
                identity=NPCIdentity(
                    entity_id=EntityId("theron"),
                    name="Theron",
                    role="guard",
                ),
                location_id=LocationId("lobby"),
            ),
        },
        locations={
            LocationId("pool"): LocationState(
                location_id=LocationId("pool"),
                name="Pool",
            ),
            LocationId("lobby"): LocationState(
                location_id=LocationId("lobby"),
                name="Lobby",
            ),
        },
        world_truth=KnowledgeState(facts={"hidden_truth": "do not expose"}),
    )


def _scene():
    return ObservableSceneBuilder().build(
        state=_world(),
        observation=SceneObservationInput(
            action=ValidatedAction(
                intent="dialogue",
                target_ids=(EntityId("victoria"),),
            ),
            subject_cues=(
                SceneSubjectCue(
                    entity_id=EntityId("victoria"),
                    position="pool_edge",
                    mood_expressions=("tense", "controlled"),
                ),
            ),
        ),
    )


def _raw(scene_id: SceneId | None = None) -> RawVST:
    actual_scene_id = SceneId("session-visual:12") if scene_id is None else scene_id
    return RawVST(
        scene_id=actual_scene_id,
        location=VSTLocationIntent(location_id=LocationId("pool")),
        subjects=(
            VSTSubjectIntent(
                entity_id=EntityId("victoria"),
                prominence=VSTSubjectProminence.PRIMARY,
                pose=SemanticIntent(description="standing beside the pool"),
            ),
        ),
        action=VSTActionIntent(
            participants=(EntityId("victoria"),),
            intent=SemanticIntent(description="direct conversation"),
        ),
        visual_focus=VSTVisualFocus(
            subject_ids=(EntityId("victoria"),),
            intent=SemanticIntent(description="primary visible subject"),
        ),
        camera=VSTCameraIntent(
            shot=SemanticIntent(description="medium shot"),
        ),
        lighting=VSTLightingIntent(
            intent=SemanticIntent(description="warm sunset light"),
        ),
        style=VSTStyleIntent(
            intent=SemanticIntent(description="cinematic realism"),
        ),
        safety=VSTSafetyIntent(signal=SafetySignal.GENERAL),
    )


def test_context_builder_exposes_only_visual_direction_inputs() -> None:
    context = VisualDirectorContextBuilder().build(_scene())
    payload = context.model_dump(mode="python")
    serialized = context.model_dump_json()

    assert payload["scene_id"] == SceneId("session-visual:12")
    assert tuple(subject.entity_id for subject in context.subjects) == (
        EntityId("player"),
        EntityId("victoria"),
    )
    assert context.subjects[1].position == "pool_edge"
    assert "Theron" not in serialized
    assert "office_code" not in serialized
    assert "hidden_truth" not in serialized
    assert "letter" not in serialized
    assert "anger" not in serialized
    assert "attraction" not in serialized
    assert "mood_expressions" not in serialized
    assert "outfit" not in serialized
    assert "visual_state" not in serialized
    assert "positive_prompt" not in serialized
    assert "negative_prompt" not in serialized


@pytest.mark.asyncio
async def test_visual_director_service_invokes_llm_once_without_libraries() -> None:
    class FakePort:
        def __init__(self) -> None:
            self.calls: list[VisualDirectorContext] = []

        async def invoke(self, request: VisualDirectorContext) -> RawVST:
            self.calls.append(request)
            return _raw(request.scene_id)

    port = FakePort()
    service = VisualDirectorService(port=port)

    result = await service.generate(_scene())

    assert result == _raw()
    assert len(port.calls) == 1
    assert port.calls[0].scene_id == SceneId("session-visual:12")


@pytest.mark.asyncio
async def test_visual_director_service_rejects_scene_id_mismatch() -> None:
    class WrongScenePort:
        async def invoke(self, request: VisualDirectorContext) -> RawVST:
            return _raw(SceneId("another-session:999"))

    service = VisualDirectorService(port=WrongScenePort())

    with pytest.raises(VSTValidationError, match="scene_id"):
        await service.generate(_scene())


def test_context_keeps_authoritative_location_and_action_semantics() -> None:
    context = VisualDirectorContextBuilder().build(_scene())

    assert context.location.location_id == LocationId("pool")
    assert context.location.name == "Pool"
    assert context.action.intent == "dialogue"
    assert context.action.target_ids == (EntityId("victoria"),)
    assert context.focus_candidate is not None
    assert context.focus_candidate.subject_ids == (EntityId("victoria"),)

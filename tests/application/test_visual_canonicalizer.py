from __future__ import annotations

from copy import deepcopy

import pytest

from epos.application.actions.models import ValidatedAction
from epos.application.visual import (
    ObservableSceneBuilder,
    SceneObservationInput,
    SceneSubjectCue,
)
from epos.application.visual.canonical import (
    VisualCanonicalizationError,
    VisualCanonicalizer,
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
from epos.application.worldpacks.models import (
    CharacterVisualCanon,
    LoadedWorldpack,
    SchedulesDocument,
    SemanticLibraryDocument,
    SemanticLibraryEntry,
    VisualDocument,
)
from epos.domain.ids import EntityId, LocationId, SceneId, SessionId, WorldpackId
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.outfit import OutfitItem, OutfitState
from epos.domain.player import PlayerState
from epos.domain.visual_state import VisualState
from epos.domain.world_state import LocationState, WorldState


def _outfit(item_id: str, name: str, color: str) -> OutfitState:
    return OutfitState(
        items=(
            OutfitItem(
                item_id=item_id,
                name=name,
                slot="body",
                layer=0,
                coverage=("torso", "hips"),
                material="linen",
                color=color,
                state="dry",
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
            outfit=_outfit("player_shirt", "linen shirt", "blue"),
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
                outfit=_outfit("victoria_dress", "summer dress", "white"),
                visual_state=VisualState(
                    traits={"wet_clothes": False, "posture": "standing"}
                ),
            ),
            EntityId("theron"): NPCState(
                identity=NPCIdentity(
                    entity_id=EntityId("theron"),
                    name="Theron",
                    role="guard",
                ),
                location_id=LocationId("lobby"),
                outfit=_outfit("theron_armor", "bronze armor", "bronze"),
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


def _library(*entries: SemanticLibraryEntry) -> SemanticLibraryDocument:
    return SemanticLibraryDocument(entries=entries)


def _entry(entry_id: str, description: str, *tags: str) -> SemanticLibraryEntry:
    return SemanticLibraryEntry(
        entry_id=entry_id,
        description=description,
        tags=tuple(tags),
    )


def _loaded_worldpack() -> LoadedWorldpack:
    return LoadedWorldpack(
        world_state=_world(),
        visual=VisualDocument(
            loras={"victoria_main": "victoria_main.safetensors"},
            characters={
                EntityId("player"): CharacterVisualCanon(
                    entity_id=EntityId("player"),
                    base_prompt="adult person",
                    role_prompt="resort guest",
                    negative_prompt="legacy player negative",
                    visual_gender="person",
                    canonical_traits=("dark hair",),
                ),
                EntityId("victoria"): CharacterVisualCanon(
                    entity_id=EntityId("victoria"),
                    base_prompt="adult woman, dark hair",
                    role_prompt="resort director",
                    negative_prompt="legacy identity negative",
                    lora_alias="victoria_main",
                    visual_gender="woman",
                    canonical_traits=("dark hair", "brown eyes"),
                ),
            },
            world_positive=("Mediterranean resort",),
            world_negative=("legacy world negative",),
        ),
        schedules=SchedulesDocument(),
        action_library=_library(
            _entry(
                "pool_conversation",
                "conversation beside pool",
                "conversation",
                "pool",
            ),
        ),
        pose_library=_library(
            _entry(
                "standing_poolside",
                "standing beside pool",
                "standing",
                "pool",
            ),
        ),
        camera_library=_library(
            _entry(
                "medium_eye_level",
                "medium shot eye level",
                "medium_shot",
                "eye_level",
            ),
        ),
        outfit_library=SemanticLibraryDocument(),
    )


def _raw() -> RawVST:
    return RawVST(
        scene_id=SceneId("session-visual:12"),
        location=VSTLocationIntent(
            location_id=LocationId("pool"),
            environment=SemanticIntent(description="outdoor pool at sunset", tags=("pool",)),
        ),
        subjects=(
            VSTSubjectIntent(
                entity_id=EntityId("victoria"),
                prominence=VSTSubjectProminence.PRIMARY,
                pose=SemanticIntent(
                    description="standing beside pool",
                    tags=("standing", "pool"),
                ),
                outfit_intent=SemanticIntent(
                    description="invented red bikini",
                    tags=("bikini", "red"),
                ),
            ),
        ),
        action=VSTActionIntent(
            participants=(EntityId("victoria"),),
            intent=SemanticIntent(
                description="conversation beside pool",
                tags=("conversation", "pool"),
            ),
        ),
        visual_focus=VSTVisualFocus(
            subject_ids=(EntityId("victoria"),),
            intent=SemanticIntent(description="Victoria is the primary visible subject"),
        ),
        camera=VSTCameraIntent(
            shot=SemanticIntent(description="medium shot", tags=("medium_shot",)),
            angle=SemanticIntent(description="eye level", tags=("eye_level",)),
        ),
        lighting=VSTLightingIntent(
            intent=SemanticIntent(description="warm sunset light", tags=("sunset",)),
        ),
        style=VSTStyleIntent(
            intent=SemanticIntent(description="cinematic realism", tags=("cinematic",)),
        ),
        safety=VSTSafetyIntent(signal=SafetySignal.GENERAL),
    )


def _canonicalize(raw: RawVST | None = None, worldpack: LoadedWorldpack | None = None):
    return VisualCanonicalizer().canonicalize(
        scene=_scene(),
        raw_vst=_raw() if raw is None else raw,
        worldpack=_loaded_worldpack() if worldpack is None else worldpack,
    )


def test_canonicalizer_replaces_invented_outfit_and_applies_visual_state() -> None:
    scene = _scene()
    before = deepcopy(scene)

    canonical = VisualCanonicalizer().canonicalize(
        scene=scene,
        raw_vst=_raw(),
        worldpack=_loaded_worldpack(),
    )

    subject = canonical.subjects[0]
    assert subject.entity_id == EntityId("victoria")
    assert subject.name == "Victoria"
    assert subject.role == "resort_director"
    assert subject.outfit == scene.visible_subjects[1].outfit
    assert subject.outfit.items[0].name == "summer dress"
    assert subject.outfit.items[0].color == "white"
    assert subject.visual_state == scene.visible_subjects[1].visual_state
    assert subject.position == "pool_edge"
    assert scene == before


def test_canonical_identity_and_lora_come_only_from_worldpack() -> None:
    canonical = _canonicalize()
    subject = canonical.subjects[0]

    assert subject.identity.base_prompt == "adult woman, dark hair"
    assert subject.identity.role_prompt == "resort director"
    assert subject.identity.visual_gender == "woman"
    assert subject.identity.canonical_traits == ("dark hair", "brown eyes")
    assert subject.lora is not None
    assert subject.lora.alias == "victoria_main"
    assert subject.lora.filename == "victoria_main.safetensors"


def test_action_pose_and_camera_are_resolved_through_worldpack_libraries() -> None:
    canonical = _canonicalize()

    assert canonical.action.semantic.entry_id == "pool_conversation"
    assert canonical.subjects[0].pose is not None
    assert canonical.subjects[0].pose.entry_id == "standing_poolside"
    assert canonical.camera.semantic.entry_id == "medium_eye_level"


def test_remote_subject_is_rejected() -> None:
    raw = _raw().model_copy(
        update={
            "subjects": (
                _raw().subjects[0],
                VSTSubjectIntent(
                    entity_id=EntityId("theron"),
                    prominence=VSTSubjectProminence.BACKGROUND,
                ),
            )
        }
    )

    with pytest.raises(VisualCanonicalizationError, match="not visible"):
        _canonicalize(raw=raw)


def test_wrong_location_is_rejected_without_hidden_llm_retry() -> None:
    raw = _raw().model_copy(
        update={
            "location": VSTLocationIntent(location_id=LocationId("lobby")),
        }
    )

    with pytest.raises(VisualCanonicalizationError, match="location"):
        _canonicalize(raw=raw)


def test_remote_action_participant_is_rejected() -> None:
    raw = _raw().model_copy(
        update={
            "action": VSTActionIntent(
                participants=(EntityId("theron"),),
                intent=_raw().action.intent,
            )
        }
    )

    with pytest.raises(VisualCanonicalizationError, match="participant"):
        _canonicalize(raw=raw)


def test_focus_must_target_a_rendered_subject() -> None:
    raw = _raw().model_copy(
        update={
            "visual_focus": VSTVisualFocus(
                subject_ids=(EntityId("player"),),
                intent=SemanticIntent(description="focus on player"),
            )
        }
    )

    with pytest.raises(VisualCanonicalizationError, match="focus"):
        _canonicalize(raw=raw)


def test_missing_visual_character_canon_is_rejected() -> None:
    worldpack = _loaded_worldpack()
    worldpack.visual.characters.pop(EntityId("victoria"))

    with pytest.raises(VisualCanonicalizationError, match="visual canon"):
        _canonicalize(worldpack=worldpack)


def test_unknown_character_lora_alias_is_rejected_explicitly() -> None:
    worldpack = _loaded_worldpack()
    victoria = worldpack.visual.characters[EntityId("victoria")]
    worldpack.visual.characters[EntityId("victoria")] = victoria.model_copy(
        update={"lora_alias": "missing_alias"}
    )

    with pytest.raises(VisualCanonicalizationError, match="LoRA alias"):
        _canonicalize(worldpack=worldpack)


def test_subject_order_follows_authoritative_scene_not_raw_llm_order() -> None:
    raw = _raw().model_copy(
        update={
            "subjects": (
                _raw().subjects[0],
                VSTSubjectIntent(
                    entity_id=EntityId("player"),
                    prominence=VSTSubjectProminence.SECONDARY,
                ),
            ),
            "visual_focus": VSTVisualFocus(
                subject_ids=(EntityId("victoria"),),
                intent=_raw().visual_focus.intent,
            ),
        }
    )

    canonical = _canonicalize(raw=raw)

    assert tuple(subject.entity_id for subject in canonical.subjects) == (
        EntityId("player"),
        EntityId("victoria"),
    )


def test_canonical_vst_preserves_dec005_boundary() -> None:
    serialized = _canonicalize().model_dump_json()

    assert "negative_prompt" not in serialized
    assert "legacy world negative" not in serialized
    assert "legacy identity negative" not in serialized
    assert "facial_expression" not in serialized
    assert "mood_expressions" not in serialized
    assert "outfit_intent" not in serialized
    assert "invented red bikini" not in serialized


def test_identical_inputs_produce_byte_identical_canonical_json() -> None:
    scene = _scene()
    raw = _raw()
    worldpack = _loaded_worldpack()
    canonicalizer = VisualCanonicalizer()

    first = canonicalizer.canonicalize(scene=scene, raw_vst=raw, worldpack=worldpack)
    second = canonicalizer.canonicalize(scene=scene, raw_vst=raw, worldpack=worldpack)

    assert first.model_dump_json() == second.model_dump_json()

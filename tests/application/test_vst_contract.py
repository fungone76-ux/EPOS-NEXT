from __future__ import annotations

import pytest
from pydantic import ValidationError

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
from epos.domain.ids import EntityId, LocationId, SceneId


def _raw_vst() -> RawVST:
    return RawVST(
        scene_id=SceneId("session-visual:12"),
        location=VSTLocationIntent(
            location_id=LocationId("pool"),
            environment=SemanticIntent(
                description="outdoor pool area at sunset",
                tags=("pool", "outdoor"),
            ),
        ),
        subjects=(
            VSTSubjectIntent(
                entity_id=EntityId("victoria"),
                prominence=VSTSubjectProminence.PRIMARY,
                pose=SemanticIntent(
                    description="standing near the pool edge",
                    tags=("standing", "pool"),
                ),
                action=SemanticIntent(
                    description="speaking to the nearby player",
                    tags=("conversation",),
                ),
                outfit_intent=SemanticIntent(
                    description="red evening dress",
                    tags=("dress", "red"),
                ),
            ),
        ),
        action=VSTActionIntent(
            participants=(EntityId("victoria"),),
            intent=SemanticIntent(
                description="conversation beside the pool",
                tags=("conversation", "pool"),
            ),
        ),
        visual_focus=VSTVisualFocus(
            subject_ids=(EntityId("victoria"),),
            intent=SemanticIntent(
                description="Victoria is the primary visual subject",
                tags=("primary_subject",),
            ),
        ),
        camera=VSTCameraIntent(
            shot=SemanticIntent(
                description="medium two shot",
                tags=("medium_shot", "two_subjects"),
            ),
            angle=SemanticIntent(
                description="eye level camera",
                tags=("eye_level",),
            ),
        ),
        lighting=VSTLightingIntent(
            intent=SemanticIntent(
                description="warm natural sunset light",
                tags=("sunset", "warm"),
            )
        ),
        style=VSTStyleIntent(
            intent=SemanticIntent(
                description="cinematic realism",
                tags=("cinematic", "realistic"),
            )
        ),
        safety=VSTSafetyIntent(signal=SafetySignal.GENERAL),
    )


def test_raw_vst_is_semantic_and_strict() -> None:
    raw = _raw_vst()

    assert raw.scene_id == SceneId("session-visual:12")
    assert raw.subjects[0].outfit_intent is not None

    payload = raw.model_dump(mode="python")
    payload["positive_prompt"] = "masterpiece, score_9"
    with pytest.raises(ValidationError, match="positive_prompt"):
        RawVST.model_validate(payload)

    payload = raw.model_dump(mode="python")
    subject = dict(payload["subjects"][0])
    subject["facial_expression"] = "seductive smile"
    payload["subjects"] = (subject,)
    with pytest.raises(ValidationError, match="facial_expression"):
        RawVST.model_validate(payload)


def test_raw_vst_cannot_carry_negative_prompt_lora_or_render_parameters() -> None:
    raw = _raw_vst()
    for field_name, value in (
        ("negative_prompt", "lowres"),
        ("lora", "victoria_main.safetensors"),
        ("checkpoint", "model.safetensors"),
        ("sampler", "dpmpp_2m"),
        ("seed", 42),
        ("cfg", 7.0),
    ):
        payload = raw.model_dump(mode="python")
        payload[field_name] = value
        with pytest.raises(ValidationError, match=field_name):
            RawVST.model_validate(payload)


def test_semantic_intent_rejects_prompt_engineering_syntax() -> None:
    forbidden = (
        "<lora:victoria:0.8>",
        "positive prompt: cinematic portrait",
        "negative prompt: lowres",
        "checkpoint=model.safetensors",
        "seed=12345",
        "cfg=7",
    )
    for text in forbidden:
        with pytest.raises(ValidationError, match=r"prompt|render"):
            SemanticIntent(description=text)


def test_raw_vst_rejects_duplicate_subjects_and_focus_ids() -> None:
    raw = _raw_vst()
    payload = raw.model_dump(mode="python")
    payload["subjects"] = (raw.subjects[0], raw.subjects[0])
    with pytest.raises(ValidationError, match="subject"):
        RawVST.model_validate(payload)

    with pytest.raises(ValidationError, match="focus"):
        VSTVisualFocus(
            subject_ids=(EntityId("victoria"), EntityId("victoria")),
            intent=SemanticIntent(description="primary subject"),
        )


def test_module_11_does_not_canonicalize_wrong_location_or_outfit() -> None:
    raw = _raw_vst().model_copy(
        update={
            "location": VSTLocationIntent(location_id=LocationId("invented_rooftop")),
            "subjects": (
                _raw_vst().subjects[0].model_copy(
                    update={
                        "outfit_intent": SemanticIntent(
                            description="invented red bikini",
                            tags=("bikini", "red"),
                        )
                    }
                ),
            ),
        }
    )

    assert raw.location.location_id == LocationId("invented_rooftop")
    assert raw.subjects[0].outfit_intent is not None
    assert raw.subjects[0].outfit_intent.description == "invented red bikini"
    # Module 12 must reject/replace these non-authoritative values.

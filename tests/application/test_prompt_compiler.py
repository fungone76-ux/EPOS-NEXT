from __future__ import annotations

from epos.application.visual.canonical import (
    CanonicalAction,
    CanonicalCamera,
    CanonicalLocation,
    CanonicalSubject,
    CanonicalVisualFocus,
    CanonicalVisualIdentity,
    CanonicalVST,
    ResolvedLora,
    ResolvedSemanticEntry,
)
from epos.application.visual.models import SceneTime, SubjectKind
from epos.application.visual.prompt import (
    FIXED_NEGATIVE_PROMPT,
    PromptCompilerProfile,
    SemanticPromptCompiler,
    WorldpackVisualConfig,
)
from epos.application.visual.vst import (
    SafetySignal,
    SemanticIntent,
    VSTLightingIntent,
    VSTSafetyIntent,
    VSTStyleIntent,
    VSTSubjectProminence,
)
from epos.application.worldpacks.models import SemanticLibraryDocument, SemanticLibraryEntry
from epos.domain.ids import EntityId, LocationId, SceneId, WorldpackId
from epos.domain.outfit import OutfitItem, OutfitState
from epos.domain.visual_state import VisualState


def _library(*entries: SemanticLibraryEntry) -> SemanticLibraryDocument:
    return SemanticLibraryDocument(entries=entries)


def _entry(
    entry_id: str,
    description: str,
    positive_fragment: str,
    *aliases: str,
) -> SemanticLibraryEntry:
    return SemanticLibraryEntry(
        entry_id=entry_id,
        description=description,
        aliases=aliases,
        positive_fragment=positive_fragment,
    )


def _canonical_vst() -> CanonicalVST:
    victoria = CanonicalSubject(
        entity_id=EntityId("victoria"),
        kind=SubjectKind.NPC,
        name="Victoria",
        role="resort_director",
        prominence=VSTSubjectProminence.PRIMARY,
        identity=CanonicalVisualIdentity(
            base_prompt="adult woman, dark hair",
            role_prompt="resort director",
            visual_gender="woman",
            canonical_traits=("dark hair", "brown eyes"),
        ),
        outfit=OutfitState(
            items=(
                OutfitItem(
                    item_id="white_summer_dress",
                    name="summer dress",
                    slot="body",
                    layer=0,
                    coverage=("torso", "hips"),
                    material="linen",
                    color="white",
                    state="dry",
                ),
            )
        ),
        visual_state=VisualState(
            traits={
                "wet_hair": True,
                "posture": "standing",
                "facial_expression": "smiling",
            }
        ),
        position="pool_edge",
        pose=ResolvedSemanticEntry(
            entry_id="pool_edge_lean",
            description="standing beside the pool",
            positive_fragment="standing, leaning lightly against the pool edge",
        ),
        lora=ResolvedLora(
            entity_id=EntityId("victoria"),
            alias="victoria_main",
            filename="victoria_main.safetensors",
        ),
    )
    return CanonicalVST(
        scene_id=SceneId("session-visual:12"),
        worldpack_id=WorldpackId("resort-world"),
        time=SceneTime(turn_number=12, day=3, world_phase="sunset"),
        location=CanonicalLocation(
            location_id=LocationId("pool"),
            name="Pool",
            environment=SemanticIntent(description="outdoor pool at sunset"),
        ),
        subjects=(victoria,),
        action=CanonicalAction(
            participants=(EntityId("victoria"),),
            semantic=ResolvedSemanticEntry(
                entry_id="pool_conversation",
                description="conversation beside pool",
                positive_fragment="conversation beside the pool",
            ),
            shared=False,
        ),
        visual_focus=CanonicalVisualFocus(
            subject_ids=(EntityId("victoria"),),
            intent=SemanticIntent(description="Victoria is the primary subject"),
        ),
        camera=CanonicalCamera(
            semantic=ResolvedSemanticEntry(
                entry_id="medium_eye_level",
                description="medium shot eye level",
                positive_fragment="medium shot, eye-level camera",
            )
        ),
        lighting=VSTLightingIntent(
            intent=SemanticIntent(description="warm sunset light", tags=("sunset",)),
        ),
        style=VSTStyleIntent(
            intent=SemanticIntent(description="cinematic realism", tags=("cinematic",)),
        ),
        safety=VSTSafetyIntent(signal=SafetySignal.GENERAL),
    )


def _config() -> WorldpackVisualConfig:
    return WorldpackVisualConfig(
        world_positive=("luxury Mediterranean resort",),
        outfit_library=_library(
            _entry(
                "white_summer_dress",
                "lightweight white summer dress",
                "white lightweight linen summer dress",
            )
        ),
        location_visual_library=_library(
            _entry(
                "pool",
                "outdoor swimming pool area of a luxury Mediterranean resort",
                "luxury Mediterranean resort swimming pool, stone pool deck",
                "resort pool",
            )
        ),
        lighting_library=_library(
            _entry(
                "warm_sunset",
                "warm natural light near sunset",
                "warm natural sunset lighting",
                "warm sunset light",
            )
        ),
        style_library=_library(
            _entry(
                "cinematic_realism",
                "realistic cinematic visual rendering",
                "cinematic realism",
                "cinematic realistic",
            )
        ),
        profile=PromptCompilerProfile(
            quality_layer=("masterpiece", "best quality"),
            checkpoint="luna_main_model.safetensors",
            width=896,
            height=1152,
            sampler="dpmpp_2m",
            scheduler="normal",
            steps=24,
            cfg=7.0,
        ),
    )


def test_compiler_builds_deterministic_layered_positive_prompt() -> None:
    compiler = SemanticPromptCompiler()

    contract = compiler.compile(_canonical_vst(), _config())

    expected_order = (
        "masterpiece",
        "best quality",
        "cinematic realism",
        "luxury Mediterranean resort",
        "luxury Mediterranean resort swimming pool, stone pool deck",
        "sunset",
        "1woman",
        "adult woman",
        "dark hair",
        "resort director",
        "brown eyes",
        "white lightweight linen summer dress",
        "wet hair",
        "standing, leaning lightly against the pool edge",
        "conversation beside the pool",
        "focus on woman",
        "medium shot, eye-level camera",
        "warm natural sunset lighting",
    )
    positions = [contract.positive_prompt.index(fragment) for fragment in expected_order]

    assert positions == sorted(positions)
    assert contract.positive_prompt.count("dark hair") == 1


def test_negative_prompt_is_exactly_the_fixed_workflow_negative() -> None:
    contract = SemanticPromptCompiler().compile(_canonical_vst(), _config())

    assert contract.negative_prompt == FIXED_NEGATIVE_PROMPT
    assert contract.negative_prompt == (
        "lowres, bad anatomy, bad hands, text, error, missing fingers, "
        "extra digit, fewer digits, cropped, worst quality, low quality, "
        "normal quality, jpeg artifacts, signature, watermark, username, blurry"
    )


def test_compiler_never_emits_facial_expression_cues() -> None:
    prompt = SemanticPromptCompiler().compile(_canonical_vst(), _config()).positive_prompt

    lowered = prompt.casefold()
    assert "facial_expression" not in lowered
    assert "smiling" not in lowered
    assert "expression" not in lowered


def test_facial_expression_atoms_are_removed_from_any_positive_layer() -> None:
    vst = _canonical_vst()
    subject = vst.subjects[0]
    contaminated_subject = subject.model_copy(
        update={
            "identity": subject.identity.model_copy(
                update={"base_prompt": "adult woman, smiling, dark hair"}
            )
        }
    )
    contaminated = vst.model_copy(update={"subjects": (contaminated_subject,)})
    config = _config().model_copy(
        update={
            "world_positive": (
                "luxury Mediterranean resort",
                "seductive expression",
            )
        }
    )

    prompt = SemanticPromptCompiler().compile(contaminated, config).positive_prompt.casefold()

    assert "smiling" not in prompt
    assert "seductive expression" not in prompt
    assert "dark hair" in prompt
    assert "brown eyes" in prompt


def test_raw_semantic_free_text_is_never_copied_directly_to_positive_prompt() -> None:
    vst = _canonical_vst().model_copy(
        update={
            "location": _canonical_vst().location.model_copy(
                update={
                    "environment": SemanticIntent(
                        description="RAW_LOCATION_INJECTION never copy me"
                    )
                }
            ),
            "visual_focus": _canonical_vst().visual_focus.model_copy(
                update={
                    "intent": SemanticIntent(description="RAW_FOCUS_INJECTION never copy me")
                }
            ),
        }
    )

    prompt = SemanticPromptCompiler().compile(vst, _config()).positive_prompt

    assert "RAW_LOCATION_INJECTION" not in prompt
    assert "RAW_FOCUS_INJECTION" not in prompt


def test_subject_count_is_derived_from_canonical_subjects() -> None:
    vst = _canonical_vst()
    second = vst.subjects[0].model_copy(
        update={
            "entity_id": EntityId("stella"),
            "name": "Stella",
            "lora": None,
        }
    )
    two_subjects = vst.model_copy(update={"subjects": (vst.subjects[0], second)})

    prompt = SemanticPromptCompiler().compile(two_subjects, _config()).positive_prompt

    assert "2women" in prompt
    assert "1woman" not in prompt


def test_lora_is_structured_and_not_in_positive_prompt() -> None:
    contract = SemanticPromptCompiler().compile(_canonical_vst(), _config())

    assert len(contract.loras) == 1
    assert contract.loras[0].alias == "victoria_main"
    assert contract.loras[0].filename == "victoria_main.safetensors"
    assert "victoria_main" not in contract.positive_prompt
    assert "<lora:" not in contract.positive_prompt


def test_render_settings_come_from_profile() -> None:
    contract = SemanticPromptCompiler().compile(_canonical_vst(), _config())

    assert contract.checkpoint == "luna_main_model.safetensors"
    assert contract.width == 896
    assert contract.height == 1152
    assert contract.sampler == "dpmpp_2m"
    assert contract.scheduler == "normal"
    assert contract.steps == 24
    assert contract.cfg == 7.0


def test_identical_inputs_produce_byte_identical_contract() -> None:
    compiler = SemanticPromptCompiler()
    vst = _canonical_vst()
    config = _config()

    first = compiler.compile(vst, config)
    second = compiler.compile(vst, config)

    assert first.model_dump_json() == second.model_dump_json()

from __future__ import annotations

from pathlib import Path

import pytest

from epos.application.visual.canonical import (
    CanonicalAction,
    CanonicalCamera,
    CanonicalLocation,
    CanonicalSubject,
    CanonicalVisualFocus,
    CanonicalVisualIdentity,
    CanonicalVST,
    SemanticLibraryResolver,
)
from epos.application.visual.models import SceneTime, SubjectKind
from epos.application.visual.prompt import (
    PromptCompilerProfile,
    SemanticPromptCompiler,
    WorldpackVisualConfig,
)
from epos.application.visual.vst import (
    SemanticIntent,
    VSTLightingIntent,
    VSTSafetyIntent,
    VSTStyleIntent,
    VSTSubjectProminence,
)
from epos.domain.ids import EntityId, LocationId, SceneId, WorldpackId
from epos.domain.outfit import OutfitItem, OutfitState
from epos.domain.visual_state import VisualState
from epos.infrastructure.worldpacks.loader import FileSystemWorldpackLoader

RESORT_ROOT = Path("worldpacks/resort_world")


@pytest.mark.asyncio
async def test_resort_libraries_resolve_common_visual_semantics() -> None:
    loaded = await FileSystemWorldpackLoader().load(
        RESORT_ROOT,
        session_id="resort-library-resolution",
    )
    resolver = SemanticLibraryResolver()

    resolved = {
        "action": resolver.resolve(
            SemanticIntent(description="walking"),
            loaded.action_library,
            library_name="action",
        ).entry_id,
        "pose": resolver.resolve(
            SemanticIntent(description="standing relaxed"),
            loaded.pose_library,
            library_name="pose",
        ).entry_id,
        "camera": resolver.resolve(
            SemanticIntent(description="medium shot"),
            loaded.camera_library,
            library_name="camera",
        ).entry_id,
        "lighting": resolver.resolve(
            SemanticIntent(description="golden hour"),
            loaded.lighting_library,
            library_name="lighting",
        ).entry_id,
        "style": resolver.resolve(
            SemanticIntent(description="cinematic"),
            loaded.style_library,
            library_name="style",
        ).entry_id,
        "location": resolver.resolve(
            SemanticIntent(description="pool"),
            loaded.location_visual_library,
            library_name="location_visual",
        ).entry_id,
    }

    assert resolved == {
        "action": "walking_forward",
        "pose": "standing_relaxed",
        "camera": "medium_shot",
        "lighting": "golden_hour",
        "style": "cinematic_realism",
        "location": "loc_pool",
    }


@pytest.mark.asyncio
async def test_python_compiles_prompt_from_real_resort_libraries() -> None:
    loaded = await FileSystemWorldpackLoader().load(
        RESORT_ROOT,
        session_id="resort-library-prompt",
    )
    resolver = SemanticLibraryResolver()
    victoria = EntityId("victoria")

    subject = CanonicalSubject(
        entity_id=victoria,
        kind=SubjectKind.NPC,
        name="Victoria",
        role="resort_director",
        prominence=VSTSubjectProminence.PRIMARY,
        identity=CanonicalVisualIdentity(
            base_prompt="adult woman",
            role_prompt="resort director",
            visual_gender="woman",
            canonical_traits=("dark hair",),
        ),
        outfit=OutfitState(
            items=(
                OutfitItem(
                    item_id="victoria_jacket",
                    name="White jacket",
                    slot="torso",
                    layer=2,
                    coverage=("torso",),
                    color="white",
                ),
            )
        ),
        visual_state=VisualState(),
        pose=resolver.resolve(
            SemanticIntent(description="standing relaxed"),
            loaded.pose_library,
            library_name="pose",
        ),
    )
    canonical = CanonicalVST(
        scene_id=SceneId("resort-library-prompt:1"),
        worldpack_id=WorldpackId("resort_world"),
        time=SceneTime(turn_number=1, day=1, world_phase="golden_hour"),
        location=CanonicalLocation(location_id=LocationId("pool"), name="Pool"),
        subjects=(subject,),
        action=CanonicalAction(
            participants=(victoria,),
            semantic=resolver.resolve(
                SemanticIntent(description="walking"),
                loaded.action_library,
                library_name="action",
            ),
        ),
        visual_focus=CanonicalVisualFocus(
            subject_ids=(victoria,),
            intent=SemanticIntent(description="Victoria"),
        ),
        camera=CanonicalCamera(
            semantic=resolver.resolve(
                SemanticIntent(description="medium shot"),
                loaded.camera_library,
                library_name="camera",
            )
        ),
        lighting=VSTLightingIntent(intent=SemanticIntent(description="golden hour")),
        style=VSTStyleIntent(intent=SemanticIntent(description="cinematic")),
        safety=VSTSafetyIntent(),
    )
    config = WorldpackVisualConfig.from_loaded_worldpack(
        loaded,
        profile=PromptCompilerProfile(),
    )

    prompt = SemanticPromptCompiler().compile(canonical, config)

    assert "cinematic realism" in prompt.positive_prompt
    assert "infinity swimming pool" in prompt.positive_prompt
    assert "standing" in prompt.positive_prompt
    assert "walking forward" in prompt.positive_prompt
    assert "medium shot" in prompt.positive_prompt
    assert "golden hour warm light" in prompt.positive_prompt

from __future__ import annotations

from pathlib import Path

import pytest

from epos.domain.errors import ConfigurationError
from epos.domain.world_state import RenderingConfig
from epos.infrastructure.rendering.a1111 import A1111RenderProfile
from epos.infrastructure.worldpacks.loader import FileSystemWorldpackLoader

ROOT = Path("worldpacks/resort_world")


@pytest.mark.asyncio
async def test_resort_declares_a1111_policy_without_machine_runtime_values() -> None:
    loaded = await FileSystemWorldpackLoader().load(ROOT, session_id="a1111-profile")
    profile = A1111RenderProfile.from_rendering_config(
        loaded.world_state.rendering_config
    )

    assert profile.default_lora_weight == 0.8
    assert profile.dimension_multiple == 8
    assert profile.min_dimension == 64
    assert profile.max_dimension == 2048

    raw = loaded.world_state.rendering_config.settings["a1111"]
    assert isinstance(raw, dict)
    assert "base_url" not in raw
    assert "checkpoint" not in raw
    assert "output_directory" not in raw


def test_missing_a1111_worldpack_policy_fails_readably() -> None:
    with pytest.raises(ConfigurationError, match="A1111 render profile"):
        A1111RenderProfile.from_rendering_config(RenderingConfig())


def test_a1111_worldpack_policy_rejects_machine_specific_fields() -> None:
    config = RenderingConfig(
        settings={
            "a1111": {
                "default_lora_weight": 0.8,
                "base_url": "http://should-not-live-in-worldpack",
            }
        }
    )

    with pytest.raises(ConfigurationError, match="invalid A1111 render profile"):
        A1111RenderProfile.from_rendering_config(config)

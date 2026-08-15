from __future__ import annotations

from pathlib import Path

import pytest

from epos.application.visual.canonical import ResolvedLora
from epos.application.visual.prompt import RenderPromptContract
from epos.domain.ids import EntityId
from epos.infrastructure.rendering.a1111 import (
    A1111AdapterSettings,
    A1111RenderProfile,
    A1111RenderRequestBuilder,
)


def _settings(tmp_path: Path) -> A1111AdapterSettings:
    return A1111AdapterSettings(
        base_url="http://127.0.0.1:7860",
        checkpoint="runtime-model.safetensors",
        output_directory=tmp_path,
    )


def test_a1111_builder_rejects_unsafe_lora_alias_instead_of_injecting_prompt_syntax(
    tmp_path: Path,
) -> None:
    contract = RenderPromptContract(
        positive_prompt="canonical scene",
        negative_prompt="fixed negative",
        loras=(
            ResolvedLora(
                entity_id=EntityId("victoria"),
                alias="victoria:1.0> BREAK <lora:evil",
                filename="victoria.safetensors",
            ),
        ),
        width=896,
        height=1152,
    )
    builder = A1111RenderRequestBuilder(
        settings=_settings(tmp_path),
        profile=A1111RenderProfile(),
    )

    with pytest.raises(ValueError, match="unsafe A1111 LoRA alias"):
        builder.build(contract, seed=1)


@pytest.mark.parametrize(
    ("width", "height"),
    ((63, 1152), (897, 1152), (896, 2056)),
)
def test_a1111_builder_rejects_dimensions_outside_worldpack_profile(
    tmp_path: Path,
    width: int,
    height: int,
) -> None:
    contract = RenderPromptContract(
        positive_prompt="canonical scene",
        negative_prompt="fixed negative",
        width=width,
        height=height,
    )
    builder = A1111RenderRequestBuilder(
        settings=_settings(tmp_path),
        profile=A1111RenderProfile(
            dimension_multiple=8,
            min_dimension=64,
            max_dimension=2048,
        ),
    )

    with pytest.raises(ValueError, match="A1111"):
        builder.build(contract, seed=1)

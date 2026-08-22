from pathlib import Path

import pytest

from epos.domain.errors import ConfigurationError
from epos.runtime.config import load_local_settings


def _project(tmp_path: Path) -> Path:
    (tmp_path / "worldpacks").mkdir()
    return tmp_path


def test_local_settings_load_dotenv_but_process_environment_wins(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / ".env").write_text(
        "EPOS_PRIMARY_LLM_MODEL=gpt-from-file\nEPOS_IMAGE_WIDTH=768\n",
        encoding="utf-8",
    )

    settings = load_local_settings(
        root,
        environ={"EPOS_PRIMARY_LLM_MODEL": "gpt-from-process"},
    )

    assert settings.environment["EPOS_PRIMARY_LLM_MODEL"] == "gpt-from-process"
    assert settings.prompt_profile.width == 768
    assert settings.default_worldpack_id == "resort_world"


def test_local_settings_resolve_project_relative_data_directory(tmp_path: Path) -> None:
    root = _project(tmp_path)

    settings = load_local_settings(root, environ={})

    assert settings.data_directory == root / "runtime_data"
    assert settings.worldpacks_directory == root / "worldpacks"


def test_local_settings_use_canonical_image_defaults(tmp_path: Path) -> None:
    root = _project(tmp_path)

    settings = load_local_settings(root, environ={})

    profile = settings.prompt_profile
    assert profile.width == 896
    assert profile.height == 1152
    assert profile.sampler == "DPM++ 2M"
    assert profile.scheduler == "Karras"
    assert profile.steps == 24
    assert profile.cfg == 7.0


def test_local_settings_allow_explicit_image_profile_overrides(tmp_path: Path) -> None:
    root = _project(tmp_path)

    settings = load_local_settings(
        root,
        environ={
            "EPOS_IMAGE_SAMPLER": "Euler a",
            "EPOS_IMAGE_SCHEDULER": "Automatic",
            "EPOS_IMAGE_STEPS": "30",
            "EPOS_IMAGE_CFG": "5.5",
        },
    )

    profile = settings.prompt_profile
    assert profile.sampler == "Euler a"
    assert profile.scheduler == "Automatic"
    assert profile.steps == 30
    assert profile.cfg == 5.5


def test_local_settings_reject_invalid_numeric_image_configuration(tmp_path: Path) -> None:
    root = _project(tmp_path)

    with pytest.raises(ConfigurationError, match="EPOS_IMAGE_WIDTH"):
        load_local_settings(root, environ={"EPOS_IMAGE_WIDTH": "wide"})
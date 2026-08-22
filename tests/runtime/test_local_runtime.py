from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from epos.application.turn import TurnCommand
from epos.application.visual.rendering import RendererHealth, RenderResult
from epos.domain.errors import ConfigurationError
from epos.domain.ids import WorldpackId
from epos.infrastructure.llm import (
    LLMProviderName,
    LLMProviderStatus,
    LLMStartupDiagnostic,
    ProviderCompletion,
)
from epos.infrastructure.llm.runtime import LLMRuntime
from epos.runtime import build_local_runtime
from epos.runtime.config import load_local_settings
from epos.runtime.local import LocalEPOSRuntime


def _environment(data_directory: Path) -> dict[str, str]:
    return {
        "EPOS_DATA_DIRECTORY": str(data_directory),
        "EPOS_RENDER_MODE": "a1111",
        "A1111_BASE_URL": "http://127.0.0.1:7860",
        "A1111_CHECKPOINT": "cyberrealisticPony_v7.safetensors",
        "EPOS_PRIMARY_LLM_PROVIDER": "openai",
        "EPOS_PRIMARY_LLM_BASE_URL": "https://api.openai.com/v1",
        "EPOS_PRIMARY_LLM_MODEL": "gpt-test",
        "EPOS_PRIMARY_LLM_KEY_ENV": "OPENAI_API_KEY",
        "OPENAI_API_KEY": "test-only-key",
        "EPOS_LLM_FALLBACK_ENABLED": "false",
    }


@pytest.mark.asyncio
async def test_local_runtime_creates_persists_and_resumes_resort_session(
    tmp_path: Path,
) -> None:
    project_root = Path.cwd()
    environment = _environment(tmp_path / "runtime_data")
    first_runtime = build_local_runtime(project_root, environ=environment)

    created = await first_runtime.create_session(WorldpackId("resort_world"))

    assert created.worldpack_id == WorldpackId("resort_world")
    assert created.location_id == "loc_lobby"
    assert (tmp_path / "runtime_data" / "current_session.txt").is_file()

    second_runtime = build_local_runtime(project_root, environ=environment)
    resumed = await second_runtime.open_default_session()

    assert resumed.session_id == created.session_id
    assert resumed == created


@pytest.mark.asyncio
async def test_local_runtime_lists_installed_worldpacks(tmp_path: Path) -> None:
    runtime = build_local_runtime(Path.cwd(), environ=_environment(tmp_path))

    worldpacks = await runtime.list_worldpacks()

    assert any(item.worldpack_id == WorldpackId("resort_world") for item in worldpacks)


def test_local_runtime_reports_missing_openai_secret_as_configuration_error(
    tmp_path: Path,
) -> None:
    environment = _environment(tmp_path)
    # Explicitly blank the secret so this test remains deterministic even when
    # the developer worktree has a real uncommitted .env file.
    environment["OPENAI_API_KEY"] = ""

    with pytest.raises(ConfigurationError, match="missing secret environment variable"):
        build_local_runtime(Path.cwd(), environ=environment)


class _ContractBackend:
    provider = LLMProviderName.OPENAI
    model = "contract-test"
    base_url = "https://example.test/v1"
    timeout_seconds = 1.0

    async def complete(self, request):
        outputs = {
            "interpret_action": (
                '{"intent":"greet","target_ids":["victoria"],'
                '"movement":null,"check":null,"outfit_request":null,"observation":null}'
            ),
            "interpret_event": (
                '{"speaker_id":"player","target_npc_id":"victoria",'
                '"topic":"greeting","mode":"brief_social"}'
            ),
            "generate_narration": (
                '{"units":[{"kind":"npc_dialogue","speaker_id":"victoria",'
                '"text":"Buongiorno, benvenuto al resort.",'
                '"evidence_ids":["reaction:victoria"]}]}'
            ),
            "audit_narration": '{"findings":[]}',
        }
        if request.task.value == "reason_npc":
            context = json.loads(request.input_json)
            text = json.dumps(
                {
                    "npc_id": context["npc_id"],
                    "intent": "answer_greeting",
                    "speech_act": "acknowledge",
                    "topic_tags": ["greeting"],
                    "emotional_tone": ["formal"],
                    "action_intent": None,
                    "target_ids": ["player"],
                    "referenced_memory_ids": [],
                    "requested_secret_disclosures": [],
                    "outfit_request_response": None,
                    "autonomous_outfit_action": None,
                }
            )
        elif request.task.value == "generate_vst":
            context = json.loads(request.input_json)
            text = json.dumps(
                {
                    "scene_id": context["scene_id"],
                    "location": {"location_id": "loc_lobby", "environment": None},
                    "subjects": [
                        {
                            "entity_id": "victoria",
                            "prominence": "primary",
                            "pose": None,
                            "action": None,
                            "body_orientation": None,
                            "outfit_intent": None,
                        }
                    ],
                    "action": {
                        "participants": ["victoria"],
                        "intent": {"description": "standing", "tags": ["standing"]},
                        "shared": False,
                    },
                    "visual_focus": {
                        "subject_ids": ["victoria"],
                        "intent": {
                            "description": "Victoria greeting the player",
                            "tags": ["greeting"],
                        },
                    },
                    "camera": {
                        "shot": {"description": "medium shot", "tags": ["medium"]},
                        "angle": None,
                        "composition": None,
                    },
                    "lighting": {
                        "intent": {"description": "morning light", "tags": ["morning"]}
                    },
                    "style": {
                        "intent": {"description": "cinematic", "tags": ["cinematic"]}
                    },
                    "safety": {"signal": "general"},
                }
            )
        else:
            text = outputs[request.task.value]
        return ProviderCompletion(provider=self.provider, model=self.model, text=text)


class _SuccessfulRenderer:
    async def render(self, request):
        return RenderResult(
            status="success",
            image_path="runtime_data/renders/turn.png",
            backend="a1111",
            prompt_id="a1111-prompt-1",
            error=None,
            duration_ms=1,
            attempts=1,
        )

    async def health_check(self):
        return RendererHealth(renderer_available=True, backend="a1111")


@pytest.mark.asyncio
async def test_local_runtime_wires_one_complete_turn_through_public_result(
    tmp_path: Path,
) -> None:
    environment = _environment(tmp_path / "runtime_data")
    settings = load_local_settings(Path.cwd(), environ=environment)
    runtime = LocalEPOSRuntime(
        settings=settings,
        llm_runtime=LLMRuntime(
            backends=(_ContractBackend(),),
            startup_diagnostic=LLMStartupDiagnostic(
                provider=LLMProviderName.OPENAI,
                model="contract-test",
                status=LLMProviderStatus.CONFIGURED,
            ),
        ),
        renderer=_SuccessfulRenderer(),  # type: ignore[arg-type]
    )
    loaded = await runtime.create_session(WorldpackId("resort_world"))
    public = await runtime.run_turn(
        loaded.session_id,
        TurnCommand(player_input="Saluto Victoria"),
    )

    assert public.narration == "Victoria Hale: Buongiorno, benvenuto al resort."
    assert public.visual.render_status == "success", public.visual.model_dump_json(indent=2)
    assert int(public.turn_number) == 1


@pytest.mark.asyncio
async def test_local_health_checks_openai_model_without_generating_tokens(
    tmp_path: Path,
) -> None:
    environment = _environment(tmp_path / "runtime_data")
    settings = load_local_settings(Path.cwd(), environ=environment)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models/contract-test"
        assert request.headers["Authorization"] == "Bearer test-only-key"
        return httpx.Response(200, json={"id": "contract-test", "object": "model"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        runtime = LocalEPOSRuntime(
            settings=settings,
            llm_runtime=LLMRuntime(
                backends=(_ContractBackend(),),
                startup_diagnostic=LLMStartupDiagnostic(
                    provider=LLMProviderName.OPENAI,
                    model="contract-test",
                    status=LLMProviderStatus.CONFIGURED,
                ),
            ),
            renderer=_SuccessfulRenderer(),  # type: ignore[arg-type]
            llm_health_client=client,
        )

        health = await runtime.health()

    assert health.llm.status == "up"
    assert health.renderer.status == "up"

from __future__ import annotations

from epos.infrastructure.llm import (
    LLMProviderName,
    LLMProviderStatus,
    OpenAICompatibleChatBackend,
    OpenAIResponsesBackend,
    build_llm_runtime_from_env,
)


def _runtime_env() -> dict[str, str]:
    return {
        "EPOS_PRIMARY_LLM_PROVIDER": "openai",
        "EPOS_PRIMARY_LLM_BASE_URL": "https://api.openai.com/v1",
        "EPOS_PRIMARY_LLM_MODEL": "primary-model",
        "EPOS_PRIMARY_LLM_KEY_ENV": "OPENAI_API_KEY",
        "OPENAI_API_KEY": "primary-secret",
        "EPOS_SECONDARY_LLM_PROVIDER": "gemini",
        "EPOS_SECONDARY_LLM_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "EPOS_SECONDARY_LLM_MODEL": "secondary-model",
        "EPOS_SECONDARY_LLM_KEY_ENV": "GEMINI_API_KEY",
        "GEMINI_API_KEY": "secondary-secret",
        "EPOS_LLM_FALLBACK_ENABLED": "true",
        "EPOS_LLM_TIMEOUT_SECONDS": "180",
    }


def test_runtime_uses_primary_secondary_base_urls_and_key_indirection() -> None:
    runtime = build_llm_runtime_from_env(_runtime_env())

    diagnostic = runtime.startup_diagnostic
    assert diagnostic.status is LLMProviderStatus.CONFIGURED
    assert diagnostic.provider is LLMProviderName.OPENAI
    assert diagnostic.model == "primary-model"
    assert diagnostic.fallback_provider is LLMProviderName.GEMINI
    assert len(runtime.backends) == 2

    primary, secondary = runtime.backends
    assert isinstance(primary, OpenAIResponsesBackend)
    assert primary.provider is LLMProviderName.OPENAI
    assert primary.model == "primary-model"
    assert primary.base_url == "https://api.openai.com/v1"
    assert primary.timeout_seconds == 180.0

    assert isinstance(secondary, OpenAICompatibleChatBackend)
    assert secondary.provider is LLMProviderName.GEMINI
    assert secondary.model == "secondary-model"
    assert secondary.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert secondary.timeout_seconds == 180.0

    dumped = diagnostic.model_dump_json()
    assert "primary-secret" not in dumped
    assert "secondary-secret" not in dumped


def test_fallback_flag_disables_secondary_even_when_fully_configured() -> None:
    environ = _runtime_env()
    environ["EPOS_LLM_FALLBACK_ENABLED"] = "false"

    runtime = build_llm_runtime_from_env(environ)

    assert len(runtime.backends) == 1
    assert runtime.startup_diagnostic.fallback_provider is None


def test_key_env_name_is_authoritative_and_may_reference_custom_secret_variable() -> None:
    environ = _runtime_env()
    environ["EPOS_PRIMARY_LLM_KEY_ENV"] = "CUSTOM_PRIMARY_KEY"
    environ["CUSTOM_PRIMARY_KEY"] = "custom-secret"
    environ.pop("OPENAI_API_KEY")

    runtime = build_llm_runtime_from_env(environ)

    assert runtime.startup_diagnostic.status is LLMProviderStatus.CONFIGURED
    assert runtime.backends[0].model == "primary-model"
    assert "custom-secret" not in runtime.startup_diagnostic.model_dump_json()


def test_missing_indirected_primary_secret_makes_llm_explicitly_unavailable() -> None:
    environ = _runtime_env()
    environ.pop("OPENAI_API_KEY")

    runtime = build_llm_runtime_from_env(environ)

    assert runtime.backends == ()
    assert runtime.startup_diagnostic.status is LLMProviderStatus.UNAVAILABLE
    assert "OPENAI_API_KEY" in runtime.startup_diagnostic.detail


def test_invalid_timeout_is_rejected_as_unavailable_configuration() -> None:
    environ = _runtime_env()
    environ["EPOS_LLM_TIMEOUT_SECONDS"] = "not-a-number"

    runtime = build_llm_runtime_from_env(environ)

    assert runtime.backends == ()
    assert runtime.startup_diagnostic.status is LLMProviderStatus.UNAVAILABLE
    assert "EPOS_LLM_TIMEOUT_SECONDS" in runtime.startup_diagnostic.detail

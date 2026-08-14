from __future__ import annotations

from epos.infrastructure.llm import (
    LLMProviderName,
    LLMProviderStatus,
    build_llm_runtime_from_env,
)


def test_gemini_can_be_primary_with_openai_as_configured_fallback() -> None:
    runtime = build_llm_runtime_from_env(
        {
            "EPOS_PRIMARY_LLM_PROVIDER": "gemini",
            "EPOS_PRIMARY_LLM_BASE_URL": "https://gemini-compatible.example/v1",
            "EPOS_PRIMARY_LLM_MODEL": "gemini-model-from-env",
            "EPOS_PRIMARY_LLM_KEY_ENV": "GEMINI_API_KEY",
            "GEMINI_API_KEY": "gemini-secret",
            "EPOS_SECONDARY_LLM_PROVIDER": "openai",
            "EPOS_SECONDARY_LLM_BASE_URL": "https://openai.example/v1",
            "EPOS_SECONDARY_LLM_MODEL": "openai-model-from-env",
            "EPOS_SECONDARY_LLM_KEY_ENV": "OPENAI_API_KEY",
            "OPENAI_API_KEY": "openai-secret",
            "EPOS_LLM_FALLBACK_ENABLED": "true",
        }
    )

    diagnostic = runtime.startup_diagnostic
    assert diagnostic.status is LLMProviderStatus.CONFIGURED
    assert diagnostic.provider is LLMProviderName.GEMINI
    assert diagnostic.model == "gemini-model-from-env"
    assert diagnostic.fallback_provider is LLMProviderName.OPENAI
    assert tuple(backend.provider for backend in runtime.backends) == (
        LLMProviderName.GEMINI,
        LLMProviderName.OPENAI,
    )


def test_unsupported_provider_fails_explicitly_without_guessing() -> None:
    runtime = build_llm_runtime_from_env(
        {
            "EPOS_PRIMARY_LLM_PROVIDER": "unknown-provider",
            "EPOS_PRIMARY_LLM_BASE_URL": "https://example.invalid/v1",
            "EPOS_PRIMARY_LLM_MODEL": "model-from-env",
            "EPOS_PRIMARY_LLM_KEY_ENV": "PRIMARY_API_KEY",
            "PRIMARY_API_KEY": "secret",
        }
    )

    diagnostic = runtime.startup_diagnostic
    assert diagnostic.status is LLMProviderStatus.UNAVAILABLE
    assert diagnostic.provider is None
    assert diagnostic.model == "model-from-env"
    assert runtime.backends == ()
    assert "unsupported EPOS_PRIMARY_LLM_PROVIDER" in diagnostic.detail


def test_model_name_is_never_synthesized_when_environment_omits_it() -> None:
    runtime = build_llm_runtime_from_env(
        {
            "EPOS_PRIMARY_LLM_PROVIDER": "gemini",
            "EPOS_PRIMARY_LLM_BASE_URL": "https://gemini-compatible.example/v1",
            "EPOS_PRIMARY_LLM_KEY_ENV": "GEMINI_API_KEY",
            "GEMINI_API_KEY": "gemini-secret",
        }
    )

    diagnostic = runtime.startup_diagnostic
    assert diagnostic.status is LLMProviderStatus.UNAVAILABLE
    assert diagnostic.provider is LLMProviderName.GEMINI
    assert diagnostic.model is None
    assert runtime.backends == ()
    assert "EPOS_PRIMARY_LLM_MODEL" in diagnostic.detail

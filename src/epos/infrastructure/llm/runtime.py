"""Environment-driven provider selection and explicit startup diagnostics."""

from __future__ import annotations

import os
from collections.abc import Mapping

from epos.infrastructure.llm.backends import (
    GeminiInteractionsBackend,
    OpenAIResponsesBackend,
    StructuredLLMBackend,
)
from epos.infrastructure.llm.models import (
    LLMProviderName,
    LLMProviderStatus,
    LLMStartupDiagnostic,
)


class LLMRuntime:
    """Immutable provider ordering plus user-visible startup diagnostic."""

    def __init__(
        self,
        *,
        backends: tuple[StructuredLLMBackend, ...],
        startup_diagnostic: LLMStartupDiagnostic,
    ) -> None:
        self._backends = backends
        self._startup_diagnostic = startup_diagnostic

    @property
    def backends(self) -> tuple[StructuredLLMBackend, ...]:
        return self._backends

    @property
    def startup_diagnostic(self) -> LLMStartupDiagnostic:
        return self._startup_diagnostic.model_copy(deep=True)


def _value(values: Mapping[str, str], name: str) -> str | None:
    raw = values.get(name)
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def _provider_variables(provider: LLMProviderName) -> tuple[str, str]:
    if provider is LLMProviderName.OPENAI:
        return "OPENAI_API_KEY", "OPENAI_MODEL"
    return "GEMINI_API_KEY", "GEMINI_MODEL"


def _make_backend(
    provider: LLMProviderName,
    *,
    api_key: str,
    model: str,
) -> StructuredLLMBackend:
    if provider is LLMProviderName.OPENAI:
        return OpenAIResponsesBackend(api_key=api_key, model=model)
    return GeminiInteractionsBackend(api_key=api_key, model=model)


def _other_provider(provider: LLMProviderName) -> LLMProviderName:
    if provider is LLMProviderName.OPENAI:
        return LLMProviderName.GEMINI
    return LLMProviderName.OPENAI


def build_llm_runtime_from_env(
    environ: Mapping[str, str] | None = None,
) -> LLMRuntime:
    """Build configured provider order without hardcoding a model or fake local LLM."""
    values = os.environ if environ is None else environ
    raw_provider = _value(values, "EPOS_LLM_PROVIDER")
    if raw_provider is None:
        return LLMRuntime(
            backends=(),
            startup_diagnostic=LLMStartupDiagnostic(
                status=LLMProviderStatus.UNAVAILABLE,
                detail="EPOS_LLM_PROVIDER is not configured; LLM unavailable",
            ),
        )

    try:
        provider = LLMProviderName(raw_provider.casefold())
    except ValueError:
        return LLMRuntime(
            backends=(),
            startup_diagnostic=LLMStartupDiagnostic(
                status=LLMProviderStatus.UNAVAILABLE,
                detail=(
                    f"unsupported EPOS_LLM_PROVIDER={raw_provider!r}; "
                    "expected openai or gemini"
                ),
            ),
        )

    key_name, model_name = _provider_variables(provider)
    api_key = _value(values, key_name)
    model = _value(values, model_name)
    missing = tuple(
        name
        for name, value in ((key_name, api_key), (model_name, model))
        if value is None
    )
    if missing:
        return LLMRuntime(
            backends=(),
            startup_diagnostic=LLMStartupDiagnostic(
                provider=provider,
                model=model,
                status=LLMProviderStatus.UNAVAILABLE,
                detail=f"missing {', '.join(missing)}; LLM unavailable",
            ),
        )

    assert api_key is not None
    assert model is not None
    backends: list[StructuredLLMBackend] = [
        _make_backend(provider, api_key=api_key, model=model)
    ]

    fallback_provider = _other_provider(provider)
    fallback_key_name, fallback_model_name = _provider_variables(fallback_provider)
    fallback_key = _value(values, fallback_key_name)
    fallback_model = _value(values, fallback_model_name)
    configured_fallback: LLMProviderName | None = None
    if fallback_key is not None and fallback_model is not None:
        backends.append(
            _make_backend(
                fallback_provider,
                api_key=fallback_key,
                model=fallback_model,
            )
        )
        configured_fallback = fallback_provider

    return LLMRuntime(
        backends=tuple(backends),
        startup_diagnostic=LLMStartupDiagnostic(
            provider=provider,
            model=model,
            status=LLMProviderStatus.CONFIGURED,
            fallback_provider=configured_fallback,
            detail="LLM configured",
        ),
    )

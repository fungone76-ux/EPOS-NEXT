"""Environment-driven primary/secondary provider selection and diagnostics."""

from __future__ import annotations

import os
from collections.abc import Mapping

from epos.infrastructure.llm.backends import (
    OpenAICompatibleChatBackend,
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


def _bool_value(values: Mapping[str, str], name: str, *, default: bool) -> bool | None:
    raw = _value(values, name)
    if raw is None:
        return default
    normalized = raw.casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _timeout(values: Mapping[str, str]) -> float | None:
    raw = _value(values, "EPOS_LLM_TIMEOUT_SECONDS")
    if raw is None:
        return 60.0
    try:
        value = float(raw)
    except ValueError:
        return None
    if value <= 0.0 or value > 600.0:
        return None
    return value


def _provider(value: str | None) -> LLMProviderName | None:
    if value is None:
        return None
    try:
        return LLMProviderName(value.casefold())
    except ValueError:
        return None


def _make_backend(
    provider: LLMProviderName,
    *,
    api_key: str,
    model: str,
    base_url: str,
    timeout_seconds: float,
) -> StructuredLLMBackend:
    if provider is LLMProviderName.OPENAI:
        return OpenAIResponsesBackend(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
    return OpenAICompatibleChatBackend(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )


def _configured_backend(
    values: Mapping[str, str],
    *,
    prefix: str,
    timeout_seconds: float,
) -> tuple[StructuredLLMBackend | None, LLMProviderName | None, str | None, str]:
    provider_name = f"EPOS_{prefix}_LLM_PROVIDER"
    base_url_name = f"EPOS_{prefix}_LLM_BASE_URL"
    model_name = f"EPOS_{prefix}_LLM_MODEL"
    key_env_name = f"EPOS_{prefix}_LLM_KEY_ENV"

    raw_provider = _value(values, provider_name)
    provider = _provider(raw_provider)
    model = _value(values, model_name)
    base_url = _value(values, base_url_name)
    key_env = _value(values, key_env_name)

    if raw_provider is not None and provider is None:
        return None, None, model, f"unsupported {provider_name}={raw_provider!r}"

    missing = tuple(
        name
        for name, value in (
            (provider_name, provider),
            (base_url_name, base_url),
            (model_name, model),
            (key_env_name, key_env),
        )
        if value is None
    )
    if missing:
        return None, provider, model, f"missing {', '.join(missing)}"

    assert provider is not None
    assert base_url is not None
    assert model is not None
    assert key_env is not None
    api_key = _value(values, key_env)
    if api_key is None:
        return None, provider, model, f"missing secret environment variable {key_env}"

    try:
        backend = _make_backend(
            provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
    except ValueError as exc:
        return None, provider, model, str(exc)
    return backend, provider, model, "configured"


def build_llm_runtime_from_env(
    environ: Mapping[str, str] | None = None,
) -> LLMRuntime:
    """Build primary/fallback LLM runtime using only environment configuration."""
    values = os.environ if environ is None else environ

    timeout_seconds = _timeout(values)
    if timeout_seconds is None:
        return LLMRuntime(
            backends=(),
            startup_diagnostic=LLMStartupDiagnostic(
                status=LLMProviderStatus.UNAVAILABLE,
                detail="invalid EPOS_LLM_TIMEOUT_SECONDS; LLM unavailable",
            ),
        )

    fallback_enabled = _bool_value(
        values,
        "EPOS_LLM_FALLBACK_ENABLED",
        default=True,
    )
    if fallback_enabled is None:
        return LLMRuntime(
            backends=(),
            startup_diagnostic=LLMStartupDiagnostic(
                status=LLMProviderStatus.UNAVAILABLE,
                detail="invalid EPOS_LLM_FALLBACK_ENABLED; LLM unavailable",
            ),
        )

    primary, primary_provider, primary_model, primary_detail = _configured_backend(
        values,
        prefix="PRIMARY",
        timeout_seconds=timeout_seconds,
    )
    if primary is None:
        return LLMRuntime(
            backends=(),
            startup_diagnostic=LLMStartupDiagnostic(
                provider=primary_provider,
                model=primary_model,
                status=LLMProviderStatus.UNAVAILABLE,
                detail=f"primary LLM unavailable: {primary_detail}",
            ),
        )

    backends: list[StructuredLLMBackend] = [primary]
    fallback_provider: LLMProviderName | None = None
    detail = "primary LLM configured"

    if fallback_enabled:
        secondary, secondary_provider, _secondary_model, secondary_detail = _configured_backend(
            values,
            prefix="SECONDARY",
            timeout_seconds=timeout_seconds,
        )
        if secondary is not None:
            backends.append(secondary)
            fallback_provider = secondary_provider
            detail = "primary and secondary LLM configured"
        elif any(
            _value(values, name) is not None
            for name in (
                "EPOS_SECONDARY_LLM_PROVIDER",
                "EPOS_SECONDARY_LLM_BASE_URL",
                "EPOS_SECONDARY_LLM_MODEL",
                "EPOS_SECONDARY_LLM_KEY_ENV",
            )
        ):
            detail = f"primary LLM configured; secondary unavailable: {secondary_detail}"

    return LLMRuntime(
        backends=tuple(backends),
        startup_diagnostic=LLMStartupDiagnostic(
            provider=primary_provider,
            model=primary_model,
            status=LLMProviderStatus.CONFIGURED,
            fallback_provider=fallback_provider,
            detail=detail,
        ),
    )

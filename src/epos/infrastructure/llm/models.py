"""Strict provider-neutral contracts for EPOS NEXT LLM infrastructure."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, JsonValue

from epos.domain.base import DomainModel


class LLMProviderName(StrEnum):
    OPENAI = "openai"
    GEMINI = "gemini"


class LLMProviderStatus(StrEnum):
    CONFIGURED = "configured"
    UNAVAILABLE = "unavailable"


class LLMTask(StrEnum):
    INTERPRET_ACTION = "interpret_action"
    INTERPRET_EVENT = "interpret_event"
    REASON_NPC = "reason_npc"
    GENERATE_NARRATION = "generate_narration"
    AUDIT_NARRATION = "audit_narration"
    GENERATE_VST = "generate_vst"
    SUMMARIZE_MEMORY = "summarize_memory"


class LLMTaskProfile(DomainModel):
    task: LLMTask
    system_instruction: str = Field(min_length=1)


class LLMRetryPolicy(DomainModel):
    """Single retry owner for one typed LLM invocation."""

    max_attempts_per_provider: int = Field(default=2, ge=1, le=3)


class LLMStartupDiagnostic(DomainModel):
    provider: LLMProviderName | None = None
    model: str | None = None
    status: LLMProviderStatus
    fallback_provider: LLMProviderName | None = None
    detail: str = ""


class StructuredLLMRequest(DomainModel):
    task: LLMTask
    system_instruction: str = Field(min_length=1)
    input_json: str = Field(min_length=1)
    schema_name: str = Field(min_length=1, max_length=64)
    json_schema: dict[str, JsonValue]


class StructuredLLMRepairInput(DomainModel):
    """Bounded feedback supplied only after a locally invalid structured response."""

    original_input_json: str = Field(min_length=1)
    invalid_output_json: str = Field(min_length=1)
    validation_errors_json: str = Field(min_length=1)


class ProviderCompletion(DomainModel):
    provider: LLMProviderName
    model: str
    text: str = Field(min_length=1)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)

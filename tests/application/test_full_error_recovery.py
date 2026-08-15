from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from epos.application.actions import CheckResolutionError
from epos.application.recovery import (
    ErrorRecoveryPolicy,
    MemoryError,
    PromptCompilationError,
    RecoveryAction,
    StateValidationError,
    VisualContractError,
)
from epos.application.visual.rendering import (
    RendererConnectionError,
    RendererExecutionError,
)
from epos.application.visual.workflow import WorkflowValidationError
from epos.application.worldpacks import WorldpackValidationError
from epos.domain.errors import ConfigurationError, PersistenceError
from epos.infrastructure.llm import LLMContractError, LLMError
from epos.infrastructure.memory.chroma import ChromaMemoryAdapter
from epos.presentation import create_app


@pytest.mark.parametrize(
    ("error", "action", "retryable", "status"),
    [
        (ConfigurationError("missing token"), RecoveryAction.RECONFIGURE, False, 503),
        (WorldpackValidationError("bad reference"), RecoveryAction.FIX_WORLDPACK, False, 422),
        (LLMError("timeout"), RecoveryAction.RETRY_TURN, True, 502),
        (LLMContractError("bad JSON"), RecoveryAction.RETRY_TURN, True, 502),
        (StateValidationError("stale state"), RecoveryAction.RESUME_SESSION, True, 409),
        (CheckResolutionError("invalid die"), RecoveryAction.RETRY_TURN, False, 422),
        (MemoryError("vector store down"), RecoveryAction.RETRY_MEMORY, True, 503),
        (VisualContractError("bad VST"), RecoveryAction.RETRY_TURN, True, 422),
        (PromptCompilationError("bad prompt input"), RecoveryAction.RETRY_TURN, True, 422),
        (WorkflowValidationError("bad graph"), RecoveryAction.FIX_WORKFLOW, False, 422),
        (RendererConnectionError("offline"), RecoveryAction.RETRY_IMAGE, True, 503),
        (RendererExecutionError("node failed"), RecoveryAction.RETRY_IMAGE, True, 502),
        (PersistenceError("disk full"), RecoveryAction.RETRY_PERSISTENCE, True, 503),
    ],
)
def test_required_error_taxonomy_has_deterministic_recovery(
    error: Exception,
    action: RecoveryAction,
    retryable: bool,
    status: int,
) -> None:
    decision = ErrorRecoveryPolicy().decide(error, phase="turn")

    assert decision.error_type == type(error).__name__
    assert decision.action is action
    assert decision.retryable is retryable
    assert decision.http_status == status
    assert decision.code
    assert decision.message


def test_post_commit_renderer_failure_preserves_turn_and_only_retries_image() -> None:
    decision = ErrorRecoveryPolicy().decide(
        RendererConnectionError("ComfyUI offline"),
        phase="visual",
        committed=True,
    )

    assert decision.action is RecoveryAction.RETRY_IMAGE
    assert decision.committed_state_preserved is True
    assert decision.replay_turn is False


def test_unexpected_error_is_reported_never_silently_swallowed() -> None:
    decision = ErrorRecoveryPolicy().decide(RuntimeError("driver exploded"), phase="visual")

    assert decision.action is RecoveryAction.REPORT_BUG
    assert decision.code == "unexpected.visual"
    assert decision.retryable is False
    assert "RuntimeError" in decision.message


class BrokenCollection:
    def add(self, record) -> None:
        raise RuntimeError("database unavailable")

    def recall(self, query, *, limit: int):
        raise RuntimeError("database unavailable")


@pytest.mark.asyncio
async def test_memory_adapter_classifies_driver_failure() -> None:
    adapter = ChromaMemoryAdapter(BrokenCollection())

    with pytest.raises(MemoryError, match="database unavailable") as raised:
        await adapter.add(object())  # type: ignore[arg-type]

    assert raised.value.code == "memory.store.failed"


class FailingRuntime:
    async def create_session(self, worldpack_id):
        raise RendererConnectionError("ComfyUI offline")


def test_api_exposes_recovery_action_for_classified_failure() -> None:
    response = TestClient(create_app(FailingRuntime())).post(
        "/sessions",
        json={"worldpack_id": "resort-world"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "renderer.connection",
        "message": "ComfyUI offline",
        "error_type": "RendererConnectionError",
        "recovery_action": "retry_image",
        "retryable": True,
        "committed_state_preserved": False,
    }

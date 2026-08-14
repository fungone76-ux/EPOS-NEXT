import pytest
from pydantic import ValidationError

from epos.domain.ids import EntityId, SessionId
from epos.domain.logging import LogContext


def test_logging_context_is_structured_and_json_serializable() -> None:
    context = LogContext(
        session_id=SessionId("s1"),
        turn_number=4,
        phase="npc_reasoning",
        provider="openai",
        npc_id=EntityId("victoria"),
        renderer=None,
    )
    assert context.model_dump(mode="json")["npc_id"] == "victoria"


def test_logging_context_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        LogContext(phase="test", surprise=True)  # type: ignore[call-arg]

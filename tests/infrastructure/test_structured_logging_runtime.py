from __future__ import annotations

from structlog.testing import capture_logs

from epos.domain.ids import EntityId, SessionId, TurnNumber
from epos.domain.logging import LogContext
from epos.infrastructure.logging import structured_logger


def test_structured_logger_binds_required_correlation_fields() -> None:
    context = LogContext(
        session_id=SessionId("session-1"),
        turn_number=TurnNumber(12),
        phase="npc_cognition",
        npc_id=EntityId("luna"),
        provider="openai",
        renderer="comfyui",
    )

    with capture_logs() as logs:
        structured_logger("epos.turn", context).info("phase_completed", duration_ms=42)

    assert logs == [
        {
            "event": "phase_completed",
            "duration_ms": 42,
            "session_id": "session-1",
            "turn_number": 12,
            "phase": "npc_cognition",
            "npc_id": "luna",
            "provider": "openai",
            "renderer": "comfyui",
            "log_level": "info",
        }
    ]

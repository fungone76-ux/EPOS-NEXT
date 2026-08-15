from __future__ import annotations

from epos.application.visual.bridge import (
    RenderRequestSnapshot,
    VisualPipelineResources,
    VisualPipelineResult,
)


def test_visual_pipeline_resources_are_backend_neutral() -> None:
    fields = set(VisualPipelineResources.model_fields)
    assert fields == {"worldpack", "prompt_profile", "seed"}
    assert "workflow_profile" not in fields
    assert "workflow_template" not in fields
    assert "workflow_parameters" not in fields


def test_visual_pipeline_result_exposes_render_request_snapshot() -> None:
    fields = set(VisualPipelineResult.model_fields)
    assert "render_request" in fields
    assert "workflow_request" not in fields


def test_render_request_snapshot_is_json_safe() -> None:
    snapshot = RenderRequestSnapshot(
        backend="a1111",
        request_id="a1111-abc123",
        payload={"seed": 42, "prompt": "canonical"},
    )
    assert snapshot.model_dump(mode="json")["payload"]["seed"] == 42

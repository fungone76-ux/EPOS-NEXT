"""Filesystem adapter for loading exported ComfyUI API workflow JSON."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from pydantic import ValidationError

from epos.application.visual.workflow import (
    ComfyWorkflowTemplate,
    WorkflowValidationError,
)


class FileSystemComfyWorkflowTemplateLoader:
    """Load one workflow template without blocking the event loop."""

    async def load(self, path: Path) -> ComfyWorkflowTemplate:
        try:
            text = await asyncio.to_thread(path.read_text, encoding="utf-8")
            raw = await asyncio.to_thread(json.loads, text)
            if not isinstance(raw, dict):
                raise WorkflowValidationError(
                    f"workflow template must be a JSON object: {path}"
                )
            prompt: dict[str, object] = {}
            for key, value in raw.items():
                if not isinstance(key, str):
                    raise WorkflowValidationError(
                        f"workflow template node id must be a string: {path}"
                    )
                prompt[key] = value
            return ComfyWorkflowTemplate.model_validate(
                {"prompt": prompt, "source": str(path)}
            )
        except WorkflowValidationError:
            raise
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise WorkflowValidationError(
                f"invalid workflow template {path}: {exc}"
            ) from exc

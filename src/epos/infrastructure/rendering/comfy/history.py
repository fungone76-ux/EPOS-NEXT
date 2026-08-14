"""Interpret completed/pending ComfyUI history payloads without leaking raw JSON upward."""

from __future__ import annotations

from typing import Literal

from pydantic import JsonValue

from epos.application.visual.rendering import RendererExecutionError, RendererProtocolError
from epos.domain.base import DomainModel


class ComfyImageReference(DomainModel):
    node_id: str
    filename: str
    subfolder: str = ""
    folder_type: str


class ComfyHistoryState(DomainModel):
    state: Literal["pending", "success"]
    image: ComfyImageReference | None = None


class ComfyHistoryInterpreter:
    def inspect(
        self,
        payload: dict[str, JsonValue],
        *,
        prompt_id: str,
    ) -> ComfyHistoryState:
        raw_entry = payload.get(prompt_id)
        if raw_entry is None:
            return ComfyHistoryState(state="pending")
        if not isinstance(raw_entry, dict):
            raise RendererProtocolError("ComfyUI history entry must be a JSON object")

        raw_status = raw_entry.get("status")
        if raw_status is None:
            return ComfyHistoryState(state="pending")
        if not isinstance(raw_status, dict):
            raise RendererProtocolError("ComfyUI history status must be a JSON object")

        status_str = raw_status.get("status_str")
        completed = raw_status.get("completed")
        if status_str == "error":
            raise RendererExecutionError(self._execution_error(raw_status))
        if completed is not True:
            return ComfyHistoryState(state="pending")
        if status_str != "success":
            raise RendererProtocolError(
                f"ComfyUI history completed with unsupported status: {status_str!r}"
            )

        image = self._output_image(raw_entry)
        if image is None:
            raise RendererExecutionError(
                "ComfyUI render completed successfully but returned no output image metadata"
            )
        return ComfyHistoryState(state="success", image=image)

    def _output_image(self, entry: dict[str, JsonValue]) -> ComfyImageReference | None:
        outputs = entry.get("outputs")
        if not isinstance(outputs, dict):
            return None

        for node_id in sorted(outputs):
            node_output = outputs[node_id]
            if not isinstance(node_output, dict):
                continue
            images = node_output.get("images")
            if not isinstance(images, list):
                continue
            for raw_image in images:
                if not isinstance(raw_image, dict):
                    continue
                filename = raw_image.get("filename")
                subfolder = raw_image.get("subfolder", "")
                folder_type = raw_image.get("type")
                if folder_type != "output":
                    continue
                if not isinstance(filename, str) or not filename.strip():
                    raise RendererProtocolError("ComfyUI output image filename is invalid")
                if not isinstance(subfolder, str):
                    raise RendererProtocolError("ComfyUI output image subfolder is invalid")
                return ComfyImageReference(
                    node_id=str(node_id),
                    filename=filename,
                    subfolder=subfolder,
                    folder_type=folder_type,
                )
        return None

    @staticmethod
    def _execution_error(status: dict[str, JsonValue]) -> str:
        messages = status.get("messages")
        if not isinstance(messages, list):
            return "ComfyUI execution failed"

        for raw_message in messages:
            if not isinstance(raw_message, list) or len(raw_message) < 2:
                continue
            event_name = raw_message[0]
            event_data = raw_message[1]
            if event_name != "execution_error" or not isinstance(event_data, dict):
                continue
            node_id = event_data.get("node_id")
            node_type = event_data.get("node_type")
            exception_type = event_data.get("exception_type")
            exception_message = event_data.get("exception_message")
            details = ["ComfyUI execution failed"]
            if isinstance(node_type, str) and node_type:
                details.append(f"node_type={node_type}")
            if isinstance(node_id, str) and node_id:
                details.append(f"node_id={node_id}")
            if isinstance(exception_type, str) and exception_type:
                details.append(f"exception_type={exception_type}")
            if isinstance(exception_message, str) and exception_message:
                details.append(exception_message)
            return "; ".join(details)
        return "ComfyUI execution failed"

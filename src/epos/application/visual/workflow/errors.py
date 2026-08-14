"""Errors owned by the Module 14 workflow boundary."""

from epos.domain.errors import EposValidationError


class WorkflowValidationError(EposValidationError):
    """A ComfyUI workflow template/profile/request is structurally incompatible."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "visual.workflow.invalid",
    ) -> None:
        super().__init__(message, code=code)

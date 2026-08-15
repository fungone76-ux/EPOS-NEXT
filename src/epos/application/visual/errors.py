"""Errors for authoritative observable-scene construction."""

from epos.domain.errors import VisualContractError


class ObservableSceneValidationError(VisualContractError):
    """Raised when a proposed observable fact contradicts the authoritative scene."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "visual.observable_scene.invalid",
    ) -> None:
        super().__init__(message, code=code)

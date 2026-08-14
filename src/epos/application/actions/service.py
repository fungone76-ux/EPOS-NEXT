"""Action-interpreter use case: LLM proposes, Python validates."""

from epos.application.actions.models import (
    ActionInterpretation,
    ActionInterpreterContext,
    ValidatedAction,
)
from epos.application.actions.validation import ActionValidator
from epos.application.ports import LLMPort


class ActionInterpreterService:
    def __init__(
        self,
        *,
        port: LLMPort[ActionInterpreterContext, ActionInterpretation],
        validator: ActionValidator,
    ) -> None:
        self._port = port
        self._validator = validator

    async def interpret(self, context: ActionInterpreterContext) -> ValidatedAction:
        proposal = await self._port.invoke(context)
        return self._validator.validate(proposal, context)

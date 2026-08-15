"""Compatibility adapters from existing application protocols to typed LLM ports."""

from epos.application.memory import MemorySummaryDraft, MemorySummaryRequest
from epos.application.ports import LLMPort


class MemorySummarizerLLMAdapter:
    """Preserve MemorySummarizerPort while routing through the generic LLMPort."""

    def __init__(
        self,
        port: LLMPort[MemorySummaryRequest, MemorySummaryDraft],
    ) -> None:
        self._port = port

    async def summarize(self, request: MemorySummaryRequest) -> MemorySummaryDraft:
        return await self._port.invoke(request)

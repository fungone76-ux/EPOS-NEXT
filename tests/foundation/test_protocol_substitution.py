from dataclasses import dataclass

import pytest

from epos.application.ports import LLMPort


@dataclass(frozen=True, slots=True)
class Prompt:
    text: str


@dataclass(frozen=True, slots=True)
class Answer:
    text: str


class FakeLLM:
    async def invoke(self, request: Prompt) -> Answer:
        return Answer(text=request.text.upper())


@pytest.mark.asyncio
async def test_generic_llm_port_accepts_structural_adapter() -> None:
    port: LLMPort[Prompt, Answer] = FakeLLM()
    result = await port.invoke(Prompt("hello"))
    assert result.text == "HELLO"

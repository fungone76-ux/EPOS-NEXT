import inspect
from collections.abc import Sequence

from epos.application.ports import (
    EmbeddingPort,
    EventBusPort,
    LLMPort,
    MemoryStorePort,
    RendererPort,
    StateStorePort,
)


def test_all_io_port_methods_are_async() -> None:
    methods = [
        LLMPort.invoke,
        RendererPort.render,
        StateStorePort.load,
        StateStorePort.save,
        MemoryStorePort.add,
        MemoryStorePort.recall,
        EventBusPort.publish,
        EmbeddingPort.embed,
    ]
    assert all(inspect.iscoroutinefunction(method) for method in methods)


def test_embedding_port_uses_batch_contract() -> None:
    signature = inspect.signature(EmbeddingPort.embed)
    assert "texts" in signature.parameters
    annotation = signature.parameters["texts"].annotation
    assert annotation == Sequence[str] or "Sequence" in str(annotation)

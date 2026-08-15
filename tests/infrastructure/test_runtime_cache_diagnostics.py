from __future__ import annotations

from pydantic import BaseModel

from epos.application.diagnostics import (
    ComponentHealthView,
    RuntimeDiagnosticsService,
)
from epos.application.visual.bridge import RenderRequestSnapshot
from epos.application.visual.canonical import CanonicalVST
from epos.application.visual.prompt import RenderPromptContract
from epos.domain.ids import SceneId, SessionId, WorldpackId
from epos.infrastructure.cache import (
    CachedStructuredLLMPort,
    ImageCacheRecord,
    SQLiteImageCache,
    SQLiteLLMCache,
    image_cache_fingerprint,
)


class Request(BaseModel):
    text: str


class Response(BaseModel):
    intent: str


class SemanticEmbeddings:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def embed(self, text: str) -> tuple[float, ...]:
        self.calls.append(text)
        if "unrelated" in text:
            return (0.0, 1.0)
        return (1.0, 0.0)


class RecordingSource:
    def __init__(self) -> None:
        self.calls: list[Request] = []

    async def invoke(self, request: Request) -> Response:
        self.calls.append(request)
        return Response(intent=f"answer-{len(self.calls)}")


async def test_llm_cache_distinguishes_exact_and_real_vector_semantic_hits(tmp_path) -> None:
    embeddings = SemanticEmbeddings()
    cache = SQLiteLLMCache(
        tmp_path / "cache.sqlite3",
        embeddings=embeddings,
        semantic_threshold=0.95,
    )
    source = RecordingSource()
    port = CachedStructuredLLMPort(
        source=source,
        cache=cache,
        response_model=Response,
        namespace="interpret_action:v1",
    )

    first = await port.invoke(Request(text="hello Luna"))
    exact = await port.invoke(Request(text="hello Luna"))
    semantic = await port.invoke(Request(text="hi Luna"))
    unrelated = await port.invoke(Request(text="unrelated weather"))

    assert first == exact == semantic
    assert unrelated.intent == "answer-2"
    assert len(source.calls) == 2
    assert cache.stats.exact_hits == 1
    assert cache.stats.semantic_hits == 1
    assert cache.stats.misses == 2
    assert cache.stats.writes == 2
    assert embeddings.calls


async def test_image_cache_uses_full_visual_fingerprint_and_round_trips(tmp_path) -> None:
    canonical = CanonicalVST.model_construct(scene_id=SceneId("scene-1"))
    prompt = RenderPromptContract(
        positive_prompt="positive",
        negative_prompt="negative",
        checkpoint="model.safetensors",
        width=896,
        height=1152,
    )
    request = RenderRequestSnapshot(
        backend="comfyui",
        request_id="request-1",
        payload={"seed": 42, "workflow_version": "v1"},
    )
    fingerprint = image_cache_fingerprint(
        canonical_vst=canonical,
        prompt_contract=prompt,
        render_request=request,
    )
    changed = image_cache_fingerprint(
        canonical_vst=canonical,
        prompt_contract=prompt,
        render_request=request.model_copy(update={"payload": {"seed": 43}}),
    )
    cache = SQLiteImageCache(tmp_path / "images.sqlite3")
    record = ImageCacheRecord(
        fingerprint=fingerprint,
        image_path="renders/image.png",
        backend="comfyui",
        prompt_id="prompt-1",
    )

    await cache.put(record)

    assert fingerprint != changed
    assert await cache.get(fingerprint) == record
    assert await cache.get(changed) is None


class HealthyProbe:
    async def check(self) -> ComponentHealthView:
        return ComponentHealthView(status="up")


class FailingProbe:
    async def check(self) -> ComponentHealthView:
        raise RuntimeError("renderer disconnected")


class Identity:
    def current_worldpack(self):
        return WorldpackId("resort-world")

    def current_session(self):
        return SessionId("session-1")


async def test_runtime_diagnostics_classifies_probe_failure_without_crashing() -> None:
    service = RuntimeDiagnosticsService(
        llm=HealthyProbe(),
        renderer=FailingProbe(),
        identity=Identity(),
    )

    health = await service.health()

    assert health.llm.status == "up"
    assert health.renderer.status == "down"
    assert health.renderer.detail == "RuntimeError: renderer disconnected"
    assert health.current_worldpack == WorldpackId("resort-world")

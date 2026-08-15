"""Ports used by the renderer-neutral visual bridge."""

from __future__ import annotations

from typing import Protocol, TypeVar

from epos.application.visual.bridge.models import BuiltRenderRequest, VisualPipelineDiagnostics
from epos.application.visual.canonical import CanonicalVST
from epos.application.visual.models import ObservableSceneState
from epos.application.visual.prompt import RenderPromptContract, WorldpackVisualConfig
from epos.application.visual.vst import RawVST
from epos.application.worldpacks.models import LoadedWorldpack

RequestT = TypeVar("RequestT")


class VisualDirectorPort(Protocol):
    async def generate(self, scene: ObservableSceneState) -> RawVST: ...


class VisualCanonicalizerPort(Protocol):
    def canonicalize(
        self,
        *,
        scene: ObservableSceneState,
        raw_vst: RawVST,
        worldpack: LoadedWorldpack,
    ) -> CanonicalVST: ...


class PromptCompilerPort(Protocol):
    def compile(
        self,
        canonical_vst: CanonicalVST,
        config: WorldpackVisualConfig,
    ) -> RenderPromptContract: ...


class RenderRequestBuilderPort(Protocol[RequestT]):
    def build(
        self,
        contract: RenderPromptContract,
        *,
        seed: int,
    ) -> BuiltRenderRequest[RequestT]: ...


class VisualDiagnosticsStorePort(Protocol):
    async def save(self, snapshot: VisualPipelineDiagnostics) -> str: ...

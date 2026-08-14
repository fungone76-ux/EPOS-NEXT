"""Filesystem/YAML adapter for strict EPOS Worldpacks."""

import asyncio
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from epos.application.worldpacks.assembler import WorldpackAssembler, WorldpackValidationError
from epos.application.worldpacks.models import (
    EventsDocument,
    LoadedWorldpack,
    LocationsDocument,
    MissionsDocument,
    NPCsDocument,
    SchedulesDocument,
    SemanticLibraryDocument,
    SkillsDocument,
    VisualDocument,
    WardrobesDocument,
    WorldDocument,
    WorldpackBundle,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class FileSystemWorldpackLoader:
    """Read YAML asynchronously, validate schemas, resolve references, build WorldState."""

    def __init__(self, assembler: WorldpackAssembler | None = None) -> None:
        self._assembler = assembler or WorldpackAssembler()

    async def load(self, root: Path, *, session_id: str) -> LoadedWorldpack:
        if not await asyncio.to_thread(root.is_dir):
            raise WorldpackValidationError(
                f"worldpack directory not found: {root}", code="worldpack.io.invalid"
            )

        bundle = WorldpackBundle(
            world=await self._required(root / "world.yaml", WorldDocument),
            locations=await self._required(root / "locations.yaml", LocationsDocument),
            npcs=await self._required(root / "npcs.yaml", NPCsDocument),
            skills=await self._required(root / "skills.yaml", SkillsDocument),
            missions=await self._optional(
                root / "missions.yaml", MissionsDocument, MissionsDocument()
            ),
            events=await self._optional(root / "events.yaml", EventsDocument, EventsDocument()),
            wardrobes=await self._optional(
                root / "wardrobes.yaml", WardrobesDocument, WardrobesDocument()
            ),
            visual=await self._optional(root / "visual.yaml", VisualDocument, VisualDocument()),
            schedules=await self._optional(
                root / "schedules.yaml", SchedulesDocument, SchedulesDocument()
            ),
            action_library=await self._optional(
                root / "action_library.yaml",
                SemanticLibraryDocument,
                SemanticLibraryDocument(),
            ),
            pose_library=await self._optional(
                root / "pose_library.yaml",
                SemanticLibraryDocument,
                SemanticLibraryDocument(),
            ),
            camera_library=await self._optional(
                root / "camera_library.yaml",
                SemanticLibraryDocument,
                SemanticLibraryDocument(),
            ),
            outfit_library=await self._optional(
                root / "outfit_library.yaml",
                SemanticLibraryDocument,
                SemanticLibraryDocument(),
            ),
        )
        return self._assembler.build(bundle, session_id=session_id)

    async def _required(self, path: Path, model: type[ModelT]) -> ModelT:
        if not await asyncio.to_thread(path.is_file):
            raise WorldpackValidationError(
                f"required worldpack file missing: {path.name}", code="worldpack.io.invalid"
            )
        return await self._load_model(path, model)

    async def _optional(self, path: Path, model: type[ModelT], default: ModelT) -> ModelT:
        if not await asyncio.to_thread(path.is_file):
            return default
        return await self._load_model(path, model)

    async def _load_model(self, path: Path, model: type[ModelT]) -> ModelT:
        try:
            text = await asyncio.to_thread(path.read_text, encoding="utf-8")
            raw = await asyncio.to_thread(_parse_yaml, text)
            return model.model_validate(raw)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            raise WorldpackValidationError(
                f"worldpack schema invalid in {path.name}: {exc}",
                code="worldpack.schema.invalid",
            ) from exc


def _parse_yaml(text: str) -> object:
    parsed: object = yaml.safe_load(text)
    if parsed is None:
        return {}
    return parsed

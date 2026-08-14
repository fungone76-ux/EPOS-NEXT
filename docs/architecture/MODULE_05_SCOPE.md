# Module 05 — Worldpacks

## Included

- strict Pydantic v2 schemas for Worldpack documents
- YAML filesystem loader with non-blocking file I/O through `asyncio.to_thread`
- required files: `world.yaml`, `locations.yaml`, `npcs.yaml`, `skills.yaml`
- optional missions, events, wardrobes, schedules, visual canon and semantic libraries
- Python cross-reference validation before a `WorldState` is constructed
- rejection of unknown NPCs, locations, skills and LoRA aliases
- rejection of invalid outfit and mission references
- Narrative Canon kept separate from Visual Canon
- Worldpack-owned skill catalogs
- `worldpacks/resort_world` and a radically different `worldpacks/test_world`
- acceptance test proving both packs load through the same engine code

## Authority rule

The Worldpack defines who and what exists. The engine defines how state, cognition, checks,
psychology, memory and rendering work. No world-specific branch belongs in `src/epos/`.

## Explicitly excluded

- schedule execution
- action interpretation and dice resolution
- NPC cognition
- visual canonicalization and prompt compilation
- concrete renderer behavior
- persistence/atomic commit orchestration

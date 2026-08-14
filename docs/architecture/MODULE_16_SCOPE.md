# Module 16 — LLM → Visual → Comfy Bridge

## Status

Module 16 connects the visual subsystems built in Modules 11–15 without moving authority between them.

The governing rule remains:

> The LLM proposes visual semantics. Python validates, canonicalizes, compiles, builds, renders, and persists diagnostics.

There is no direct LLM → ComfyUI path.

## Mandatory pipeline

```text
ObservableSceneState
        ↓
Visual Director Port
        ↓
RAW VST
        ↓
Visual Canonicalizer
        ↓
Canonical VST
        ↓
Prompt Compiler
        ↓
RenderPromptContract
        ↓
Comfy Workflow Builder
        ↓
ComfyWorkflowRequest
        ↓
RendererPort / ComfyUI Adapter
        ↓
RenderResult
```

`VisualTurnPipeline` is deliberately a thin coordinator. It contains no provider-specific LLM logic, no semantic-library matching algorithm, no prompt syntax rules, no Comfy graph mutation logic, and no HTTP client logic.

## Dependencies

The bridge depends on replaceable ports/contracts:

- `VisualDirectorPort`;
- `VisualCanonicalizerPort`;
- `PromptCompilerPort`;
- existing `ComfyWorkflowBuilderPort`;
- existing `RendererPort[ComfyWorkflowRequest]`;
- `VisualDiagnosticsStorePort`.

This keeps Module 17 free to supply OpenAI/Gemini implementations without changing the visual pipeline.

## Visual resources

`VisualPipelineResources` contains only already-resolved resources needed for one visual pass:

- active `LoadedWorldpack`;
- `PromptCompilerProfile`;
- `ComfyWorkflowProfile`;
- loaded `ComfyWorkflowTemplate`;
- per-render `ComfyWorkflowBuildParameters` such as client ID and seed.

The bridge does not receive raw player input, mutable WorldState, a Stable Diffusion prompt string, or an LLM prompt.

## Semantic libraries

Semantic-library content remains Worldpack-owned.

The bridge does not hardcode or copy library entries.

The active `LoadedWorldpack` is passed intact to the Visual Canonicalizer, which owns resolution of the canonical action/pose/camera semantics. The bridge then constructs `WorldpackVisualConfig` through `WorldpackVisualConfig.from_loaded_worldpack(...)`, which supplies the Prompt Compiler with the Worldpack visual base and the prompt-facing libraries such as outfit, lighting, location visual, and style.

Therefore replacing or expanding the authored library YAML files changes visual content without changing `VisualTurnPipeline`.

The currently supported Worldpack visual semantic files remain:

```text
action_library.yaml
pose_library.yaml
camera_library.yaml
outfit_library.yaml
lighting_library.yaml
location_visual_library.yaml
style_library.yaml
```

Module 16 makes no assumptions about their actual entries.

## Diagnostics before rendering

Before the renderer is called, the bridge persists a `prepared` visual snapshot containing:

- scene ID;
- RAW VST;
- Canonical VST;
- complete `RenderPromptContract` including positive, fixed negative, LoRA data and generation settings;
- complete `ComfyWorkflowRequest`.

This ordering is intentional:

```text
compile complete visual contract
        ↓
atomic diagnostics save
        ↓
renderer submission
```

If the prepared diagnostics cannot be saved safely, the renderer is not called. EPOS must not submit an external render job without retaining the deterministic contract needed to diagnose or recover it.

## Diagnostics after rendering

After `RendererPort.render(...)` returns, the same scene diagnostics file is atomically replaced with a `rendered` snapshot that additionally contains the complete `RenderResult`, including the Comfy `prompt_id` when one exists.

A final diagnostics-write failure does not trigger a second renderer call. The bridge returns the already-obtained `RenderResult` together with `diagnostics_error` and the last successfully persisted diagnostics path.

This prevents a persistence acknowledgement problem from creating duplicate Comfy jobs.

## Atomic diagnostics store

`AtomicVisualDiagnosticsStore`:

- derives a deterministic safe filename from `scene_id`;
- serializes strict Pydantic contracts as sorted JSON;
- writes through the engine's existing atomic byte-write primitive using `asyncio.to_thread`;
- maps filesystem and persistence failures to `VisualDiagnosticsPersistenceError`.

Example filename:

```text
session_12.visual.json
```

The prepared snapshot and final rendered snapshot intentionally use the same path. Later render recovery can treat it as the latest authoritative visual contract for that scene.

## Failure semantics

The visual bridge does not own narrative state and cannot mutate or roll back it.

A failed renderer result is returned and persisted as visual failure data. The future Turn Orchestrator owns the policy that a completed narrative turn remains valid when rendering fails.

The bridge deliberately does not introduce a second retry layer:

- the Visual Director is invoked once per pipeline run;
- the Canonicalizer is invoked once;
- prompt compilation is deterministic;
- workflow construction is deterministic;
- `RendererPort.render(...)` is invoked once;
- renderer-level pre-acceptance retry policy remains owned by Module 15.

Once Module 15 has obtained a Comfy `prompt_id`, no bridge behavior resubmits the job automatically.

## Retry Image preparation

Module 20 will own the explicit `Retry Image` command.

Module 16 persists enough information before the first render to allow that future operation to reuse the visual contract without:

- a new player turn;
- a new Visual Director LLM call;
- new NPC cognition;
- new dice;
- new world mutation;
- prompt recompilation from newly invented semantics.

The exact restart/recovery service is intentionally not implemented here.

## Product visual decisions preserved

Module 16 does not modify the output of Module 13.

Therefore:

- the negative prompt remains the single fixed canonical negative;
- no dynamic character/world negative layer is added;
- no facial-expression layer is introduced;
- LoRAs remain Python-resolved structured data before workflow construction.

## Explicit exclusions

Module 16 does not implement:

- OpenAI/Gemini providers or provider fallback — Module 17;
- complete game-turn orchestration — Module 18;
- final `TurnResult` presentation contract — Module 19;
- explicit Retry Image/restart recovery — Module 20;
- GUI — Module 21;
- FastAPI — Module 22;
- global cache/logging/diagnostics aggregation — Module 23;
- whole-engine crash recovery — Module 24.

## Acceptance boundary

Module 16 is complete when tests prove that:

1. the stages execute in the mandatory order;
2. no direct LLM → prompt or LLM → Comfy shortcut exists in the bridge contract;
3. the full deterministic visual contract is persisted before renderer submission;
4. renderer failure is retained without a second Visual Director invocation;
5. a pre-render diagnostics failure prevents external submission;
6. a post-render diagnostics failure cannot duplicate the render;
7. diagnostics are written atomically and replace the prepared snapshot with the rendered snapshot;
8. pytest, Ruff, and mypy strict remain green.

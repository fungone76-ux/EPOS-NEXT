# Module 14 — ComfyUI Workflow Builder

## Status

Module 14 converts the deterministic `RenderPromptContract` from Module 13 into a validated ComfyUI API workflow request.

It does not call ComfyUI. Network submission and image retrieval belong to Module 15.

## Pipeline position

```text
CanonicalVST
    ↓
Module 13 Prompt Compiler
    ↓
RenderPromptContract
    +
Worldpack ComfyUI profile
    +
ComfyUI API workflow template
    +
Python-owned build parameters (client_id / seed)
    ↓
Module 14 ComfyWorkflowBuilder
    ↓
ComfyWorkflowRequest
    ↓
Module 15 ComfyUI Adapter
```

## Architectural boundary

The application layer owns strict contracts and ports under:

```text
src/epos/application/visual/workflow/
```

The Comfy-specific JSON manipulation and filesystem template loading live under:

```text
src/epos/infrastructure/rendering/comfy/
```

This keeps later orchestration dependent on application ports instead of concrete infrastructure classes.

## No hardcoded node IDs in the engine

The engine does not assume that prompt, sampler, scheduler, latent or LoRA nodes use any particular IDs.

A `ComfyWorkflowProfile` supplied by the active Worldpack declares:

- workflow file;
- base checkpoint node and its model/CLIP output indexes;
- runtime-editable input bindings;
- ordered LoRA slots;
- optional per-LoRA strength rules;
- dimension policy.

The current Resort profile happens to map the supplied workflow as follows:

```text
checkpoint       node 1
positive prompt  node 2
negative prompt  node 3
seed / cfg       node 4
sampler          node 5
scheduler/steps  node 6
width/height     node 7
LoRA slots       nodes 20, 23
```

These IDs are Worldpack content, not engine constants.

If another workflow uses 2, 6 or 10 LoRA loader nodes, the core builder remains unchanged; only the Worldpack profile changes.

## Canonical Resort workflow

The user-supplied API-format `comfy_workflow_image.json` is retained in:

```text
worldpacks/resort_world/workflows/comfy_workflow_image.json
```

The exact supplied file contains LoRA loader nodes `20` and `23`. Module 14 therefore does not assume a previously discussed `20..25` range.

The workflow profile is declared under:

```text
worldpacks/resort_world/world.yaml
rendering_config.comfyui
```

`ComfyWorkflowProfile.from_rendering_config(...)` converts that generic Worldpack configuration into the strict typed profile and fails readably if it is missing or invalid.

## Authorized runtime mutations

Module 14 may change only the runtime-controlled values declared by the profile:

- positive prompt;
- negative prompt;
- checkpoint, when provided by `RenderPromptContract`;
- seed;
- CFG, when provided;
- sampler, when provided;
- scheduler, when provided;
- steps, when provided;
- width;
- height;
- configured LoRA chain.

The builder operates on a deep copy of the template. The original template is never mutated.

Unrelated nodes such as VAE decode and image save remain untouched.

## Optional render settings

`RenderPromptContract` may leave checkpoint, CFG, sampler, scheduler or steps unset.

When one of those values is `None`, Module 14 validates the existing template value and preserves it rather than inventing a replacement.

The seed is different: it is supplied explicitly as a Python-owned `ComfyWorkflowBuildParameters.seed` for each render build and always replaces the template seed.

This keeps random render state outside the LLM.

## Dimension validation

Dimensions are validated against the Worldpack profile before the workflow is returned.

The profile controls:

- minimum dimension;
- maximum dimension;
- required multiple.

The Resort profile currently uses:

```text
min = 64
max = 2048
multiple = 8
```

The core does not embed these values as global truths.

## LoRA authority and chain rebuilding

The `RenderPromptContract.loras` tuple is authoritative for the LoRAs that should be active for the render.

Template-resident LoRAs are not implicitly trusted.

Module 14 therefore rebuilds the configured LoRA chain from the structured contract.

For each requested LoRA, Python controls:

- resolved filename;
- ordered slot assignment;
- model strength;
- CLIP strength;
- model input connection;
- CLIP input connection.

Per-alias strength rules may be declared in the Worldpack profile. Otherwise profile defaults are used.

The LLM never writes LoRA syntax and never chooses workflow node IDs.

## Unused LoRA slots

Configured LoRA nodes that are not required by the current `RenderPromptContract` are removed from the generated request.

All configured downstream references are then rewired to the final active LoRA node, or directly to the base checkpoint when no LoRA is active.

This prevents template leftovers such as:

```text
<lora_name>
detail_slider_v4.safetensors
```

from becoming active merely because they were present in the exported template.

With zero active LoRAs, the current Resort workflow is rewired so prompt encoders and model consumers receive the base checkpoint model/CLIP directly.

With one active LoRA, configured consumers receive that single LoRA output.

With two active LoRAs, nodes `20 -> 23` form the ordered chain and configured consumers receive node `23` outputs.

## Graph safety

Before returning a request, the builder verifies:

- every workflow node is an object;
- every node has a non-blank `class_type`;
- every node has an `inputs` object;
- the base checkpoint node exists and has the expected class;
- every configured runtime binding exists;
- every configured binding points to the expected node class;
- existing preserved prompt/checkpoint/sampler/scheduler/step/cfg values have valid scalar types;
- every configured LoRA slot has the expected class and required inputs;
- requested LoRA count does not exceed configured slots;
- requested LoRA aliases are unique;
- requested aliases and filenames are non-blank;
- no removed LoRA node remains referenced;
- references to unsupported LoRA output indexes fail explicitly.

The builder never silently returns a known-broken graph.

## Template loading

`FileSystemComfyWorkflowTemplateLoader` loads API workflow JSON behind an async port.

Blocking file reading is executed through `asyncio.to_thread`.

Invalid JSON, unreadable files, invalid top-level structure or Pydantic validation failures become readable `WorkflowValidationError` failures.

## Determinism

Given identical:

- `RenderPromptContract`;
- `ComfyWorkflowTemplate`;
- `ComfyWorkflowProfile`;
- `ComfyWorkflowBuildParameters`;

Module 14 produces byte-identical `ComfyWorkflowRequest.model_dump_json()` output.

The Resort integration test builds the real workflow twice and verifies this property.

## Product decisions preserved

Module 14 does not reinterpret prompt content.

Therefore the Module 13 decisions remain intact:

- negative prompt is the fixed canonical value already present in the `RenderPromptContract`;
- no facial-expression prompt layer is added;
- LoRAs remain structured rather than being inserted into positive prompt text.

## Failure behavior

Module 14 fails closed for structural incompatibility.

Typical failures include:

- missing Worldpack ComfyUI profile;
- invalid profile schema;
- missing workflow file;
- malformed JSON;
- missing required node;
- wrong node type;
- missing runtime input;
- blank checkpoint override;
- invalid dimensions;
- too many requested LoRAs;
- duplicate requested LoRA aliases;
- dangling/unsupported LoRA graph references.

These errors happen before any HTTP call to ComfyUI.

## Explicit exclusions

Module 14 does not implement:

- ComfyUI HTTP submission;
- websocket progress handling;
- prompt/job polling;
- image download;
- render timeout/retry;
- render result persistence;
- image retry UX;
- LLM provider calls;
- VST retry orchestration.

Those responsibilities remain in Modules 15+.

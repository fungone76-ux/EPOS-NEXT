# Module 13 — Deterministic Prompt Compiler

## Status

Module 13 converts a Python-authoritative `CanonicalVST` into a strict `RenderPromptContract` for later ComfyUI workflow construction.

The governing rule remains:

> The LLM may propose visual semantics. Python compiles the Stable Diffusion prompt.

No LLM call occurs in this module.

## Position in the visual pipeline

```text
CanonicalVST
    +
LoadedWorldpack visual libraries
    +
PromptCompilerProfile
        ↓
WorldpackVisualConfig
        ↓
SemanticPromptCompiler
        ↓
RenderPromptContract
        ↓
Module 14 Workflow Builder
```

`WorldpackVisualConfig.from_loaded_worldpack(...)` builds an isolated compiler view using deep copies of the relevant libraries and a separate render profile.

## RenderPromptContract

The output contains:

- deterministic `positive_prompt`;
- fixed `negative_prompt`;
- structured resolved LoRAs;
- checkpoint selection from the render profile;
- width / height;
- sampler / scheduler;
- steps;
- CFG.

LoRAs remain structured data. Module 13 does not inject `<lora:...>` syntax into the positive prompt.

## Product Owner overrides

The latest Product Owner decisions override the older modular specification where they conflict.

### Fixed negative prompt

EPOS NEXT uses exactly one runtime negative prompt for the canonical workflow:

```text
lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry
```

The compiler does not dynamically append:

- Worldpack negative fragments;
- character negative fragments;
- emotion-specific negatives;
- scene-specific negatives;
- LLM-generated negatives.

Existing legacy `world_negative` and character `negative_prompt` fields may remain in Worldpack data for compatibility but are not consumed by Module 13.

### No facial-expression prompt layer

The older specification described facial/expression cues as one possible positive-prompt layer. That layer is disabled by Product Owner decision.

The compiler filters facial-expression atoms from every positive source, not only `VisualState`.

Examples that are removed include semantic atoms such as:

- smiling / smile;
- frowning / frown;
- grin / smirk;
- facial expression / expression;
- mouth directives;
- eyebrow directives;
- furrowed brows;
- emotional face directives such as angry face or seductive face.

Canonical identity traits such as `brown eyes` are not removed merely because they describe appearance.

`VisualState` keys associated with face, facial expression, mood, emotion or posture are also excluded from positive-prompt compilation.

## Seven visual semantic libraries

The Worldpack loader now supports all seven visual libraries:

```text
action_library.yaml
pose_library.yaml
camera_library.yaml
outfit_library.yaml
lighting_library.yaml
location_visual_library.yaml
style_library.yaml
```

The new three libraries are optional for backward compatibility until existing Worldpacks are populated.

Each semantic entry supports:

```yaml
- entry_id: canonical_unique_id
  description: human readable semantic description
  aliases:
    - natural language equivalent
  tags:
    - semantic_tag
  positive_fragment: "stable diffusion positive prompt fragment"
```

`aliases` and `positive_fragment` are validated as authored Worldpack data. Duplicate aliases in one entry are rejected after normalization.

## Semantic resolution

The deterministic resolver now uses authored evidence in this order:

1. exact normalized `entry_id`;
2. exact normalized alias;
3. exact authored `positive_fragment`;
4. exact normalized description;
5. deterministic tag / lexical evidence scoring.

For non-exact lexical matching, a single generic shared word is insufficient unless authored tag evidence also supports the entry.

No candidate fails closed.

Equal best candidates fail as ambiguous.

The `positive_fragment` copied into `ResolvedSemanticEntry` always comes from the authored library entry, never from LLM free text.

## Positive prompt order

The compiler assembles positive layers in a stable order:

1. render-profile quality layer;
2. canonical style fragment;
3. Worldpack positive style/base fragments;
4. canonical location visual fragment;
5. canonical world phase/time tag;
6. deterministic subject-count tags;
7. per-subject canonical identity base;
8. per-subject role;
9. per-subject canonical traits;
10. authoritative outfit fragments;
11. allowed deterministic `VisualState` fragments;
12. canonical pose / subject action / body orientation;
13. canonical scene action;
14. deterministic visual-focus tag;
15. canonical camera fragment;
16. canonical lighting fragment.

Prompt atoms are normalized, de-duplicated case-insensitively, and kept in first-authorized-occurrence order.

Therefore identical canonical inputs and identical configuration produce byte-identical `RenderPromptContract` JSON.

## No raw LLM text passthrough

Module 13 never copies `CanonicalLocation.environment` prose or `CanonicalVisualFocus.intent` prose directly into the positive prompt.

Location, style and lighting free semantic descriptions must resolve against their authored libraries when those libraries are configured.

Action, pose and camera arrive from Module 12 as already-resolved semantic entries carrying authored positive fragments.

This prevents a RAW VST sentence from becoming a Stable Diffusion prompt merely because it survived as semantic context.

## Outfit authority

Outfit choice remains Python-authoritative.

The compiler receives `CanonicalSubject.outfit`, which was already corrected against `ObservableSceneState` by Module 12.

For each real outfit item, Module 13 attempts an authored `outfit_library` translation by item ID, name or alias.

If no library translation exists, Python emits a deterministic fallback from the authoritative item's own canonical fields. It never uses the LLM's discarded `outfit_intent`.

## VisualState

Allowed visible state is compiled deterministically.

Examples can include state such as wet hair, wet clothing, dirt or similar non-facial visual conditions represented in the canonical state.

Internal emotion is never inferred from `VisualState` and facial-expression / mood / emotion / posture keys are excluded from this prompt layer.

## Subject counting

Character counts are derived from the canonical rendered subject list, not from LLM prose.

The default profile supports configurable grammar such as:

```text
1woman
2women
1man
2men
1person
2people
```

The grammar is profile-owned rather than hardwired into WorldState or a specific Worldpack.

## LoRA handling

LoRAs come only from the resolved canonical subjects produced by Module 12.

Module 13:

- preserves authorized alias + filename;
- de-duplicates repeated alias/filename pairs in stable order;
- never invents a LoRA;
- never turns the alias into arbitrary positive-prompt text.

Module 14 will place these structured LoRAs into authorized workflow slots.

## Render profile authority

Checkpoint and inference settings belong to `PromptCompilerProfile`, not to the engine globally.

The canonical supplied workflow can therefore use values such as:

```text
checkpoint = luna_main_model.safetensors
width = 896
height = 1152
sampler = dpmpp_2m
scheduler = normal
steps = 24
cfg = 7
```

without making `luna_main_model.safetensors` a permanent global engine truth.

Different Worldpacks / renderer profiles remain replaceable.

## Loader integration

`FileSystemWorldpackLoader` reads all seven optional library files and the assembler carries them into `LoadedWorldpack`.

An infrastructure regression test writes all seven files to a temporary Worldpack directory, loads them through the real filesystem adapter, and verifies that aliases / positive fragments survive loading.

The same test verifies the isolated `LoadedWorldpack -> WorldpackVisualConfig` wiring.

## Determinism and test boundaries

Module 13 verifies:

- deterministic positive-layer order;
- exact fixed negative prompt;
- no facial-expression leakage from `VisualState`;
- no facial-expression leakage from any positive source;
- no direct RAW semantic location/focus prose leakage;
- subject-count derivation from canonical subjects;
- structured LoRA output with no `<lora:...>` prompt injection;
- render-profile settings propagation;
- byte-identical contract for identical input;
- seven-library schema compatibility;
- seven-library real filesystem loading;
- deep-copy isolation of compiler configuration.

## Explicit exclusions

Module 13 does not:

- mutate the ComfyUI workflow;
- choose workflow node IDs dynamically;
- send HTTP requests to ComfyUI;
- wait for image completion;
- download or persist rendered image bytes;
- run an LLM;
- retry visual interpretation;
- mutate WorldState.

Those responsibilities remain in Modules 14–16 and later orchestration/recovery modules.

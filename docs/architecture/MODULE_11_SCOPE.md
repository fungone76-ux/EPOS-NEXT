# Module 11 — Visual Semantic Table Generator

## Status

Module 11 introduces the typed boundary between the disclosure-safe `ObservableSceneState`
and a future concrete Visual Director LLM provider.

The governing rule remains:

> The LLM interprets visual intent. Python governs visual truth and later compiles the render prompt.

## Purpose

Module 11 produces a **RAW VST** (Visual Semantic Table). It does not canonicalize world
facts and it does not generate Stable Diffusion/ComfyUI prompts.

```text
ObservableSceneState
        ↓
VisualDirectorContextBuilder
        ↓
VisualDirectorContext
        ↓
LLMPort[VisualDirectorContext, RawVST]
        ↓
RawVST
        ↓
RawVSTValidator
        ↓
Module 12 Visual Canonicalizer
```

A concrete OpenAI/Gemini provider remains deferred to the provider module. Tests use typed
fake ports.

## Visual Director context

The Visual Director receives only information needed to make semantic composition choices:

- canonical `scene_id`;
- observable location;
- canonical game time;
- visible subject identity, role and optional coarse position;
- validated action intent and visible targets;
- already-resolved Python check outcome, when applicable;
- observable consequences;
- conservative visual-focus candidate;
- dialogue speaker/target cues without dialogue text.

The context deliberately does **not** expose:

- `WorldState.world_truth`;
- NPC knowledge, beliefs, false beliefs, secrets or memories;
- relationship or intimacy state;
- internal emotional values;
- observable `mood_expressions`;
- authoritative outfit data;
- authoritative `VisualState`;
- LoRA aliases or filenames;
- checkpoint/sampler/seed/CFG;
- positive or negative prompt text.

Authoritative outfit and visual identity remain available to Python downstream through the
observable scene/worldpack path, not through LLM visual invention.

## Raw VST contract

`RawVST` is strict Pydantic data with `extra="forbid"` inherited from `DomainModel`.
It contains:

- `scene_id`;
- semantic location intent;
- semantic subject intents;
- semantic scene action;
- semantic visual focus;
- semantic camera intent;
- semantic lighting intent;
- semantic style intent;
- a non-authoritative safety classification.

Subject direction may contain semantic pose/action/body-orientation suggestions. A raw
`outfit_intent` is accepted only as an explicitly non-authoritative proposal so Module 12 can
prove that invented or incorrect outfit content is replaced by Python-authoritative state.
It is never render truth.

## SemanticIntent is not a Stable Diffusion prompt

Every free semantic fragment is wrapped in `SemanticIntent` and kept short. The schema
rejects common prompt/render-control syntax including:

- LoRA syntax;
- `positive prompt` / `negative prompt` instructions;
- checkpoint directives;
- sampler directives;
- seed directives;
- CFG directives;
- common direct quality-prompt markers such as `masterpiece` / `score_*`.

This is a defense-in-depth boundary. The LLM describes meaning; it does not write the render
language.

## Product-owner facial-expression rule

Per DEC-005, Module 11 exposes **no facial-expression output field**.

It also strips `ObservableSceneState.mood_expressions` from `VisualDirectorContext`. This is
intentional: psychological/emotional state may influence gameplay and narration, but it is
not translated into facial Stable Diffusion instructions.

Later prompt compilation must not introduce a facial-expression layer.

## Product-owner fixed-negative rule

Module 11 contains no negative-prompt field at all.

Per DEC-005, the render pipeline will use one fixed canonical negative prompt from the
approved workflow/render profile. Runtime world, character, scene, emotion or LLM output
must not dynamically extend that negative prompt.

The actual fixed negative is wired by the later Prompt Compiler / Workflow Builder modules,
not by Module 11.

## No semantic libraries required yet

Module 11 intentionally does not depend on action/pose/camera/lighting/location/outfit/style
libraries.

This lets the Visual Director produce RAW semantic intent while those libraries are authored
independently.

The libraries become authoritative inputs to **Module 12**, where Python maps semantic intent
to canonical entries and rejects/replaces incompatible proposals.

The intended ranking/canonicalization policy is:

```text
exact canonical id / alias
→ compatible tags
→ scene/world compatibility
→ semantic similarity
→ minimum confidence threshold
→ safe fallback or explicit validation failure
```

Semantic similarity alone is never authority.

## Module boundary: why incorrect raw values may exist

The RAW VST is a proposal, not truth. Therefore Module 11 may receive an invented location or
outfit suggestion from a malformed/overreaching LLM response.

Module 11 validates schema and binds the response to the same `scene_id`, but does not silently
pretend the proposal is authoritative.

Module 12 owns the world-aware checks and corrections, including:

- real location;
- real visible subjects;
- canonical character identity;
- authoritative outfit;
- canonical visual/body state;
- semantic-library mapping;
- camera policy;
- authorized LoRA aliases.

This keeps the acceptance case explicit:

```text
LLM proposes wrong outfit
→ RAW VST records the proposal
→ Module 12 compares against authoritative state
→ Python replaces/rejects it
→ Canonical VST contains only the real outfit
```

## Safety field

`VSTSafetyIntent` is semantic classification only. It never grants consent, adult status,
body coverage, nudity, intimacy authorization or any other state authority.

Those remain Python-authoritative.

## Explicit exclusions

Module 11 does not implement:

- semantic-library matching;
- canonical VST;
- Stable Diffusion positive prompt compilation;
- negative prompt composition;
- LoRA resolution;
- ComfyUI workflow injection;
- renderer calls;
- concrete OpenAI/Gemini API adapters.

Those remain downstream responsibilities.

# Module 12 — Visual Canonicalizer

## Status

Module 12 converts the non-authoritative RAW VST produced by Module 11 into a Python-authoritative `CanonicalVST` suitable for deterministic prompt compilation.

The governing rule remains:

> The LLM interprets and proposes visual semantics. Python governs visual truth.

## Position in the pipeline

```text
ObservableSceneState
        +
RAW VST
        +
LoadedWorldpack visual canon / LoRA registry / semantic libraries
        ↓
VisualCanonicalizer
        ↓
CanonicalVST
        ↓
Module 13 Prompt Compiler
```

Module 12 does not call an LLM and does not render an image.

## Authority split

`ObservableSceneState` is the current runtime source of truth for:

- scene identity;
- worldpack identity;
- turn/day/world phase;
- current location;
- current visible presence;
- entity name and role;
- authoritative outfit;
- authoritative `VisualState`;
- already-authorized fine position cues.

`LoadedWorldpack` is used only for stable content definitions needed by the visual system:

- `CharacterVisualCanon`;
- LoRA alias registry;
- action semantic library;
- pose semantic library;
- camera semantic library;
- other visual-library content exposed by the Worldpack contract.

The initial `LoadedWorldpack.world_state` is not treated as the current mutable runtime world. Its `worldpack_id` is only cross-checked against the observable scene.

## CanonicalVST binding

The canonical contract carries its own authoritative binding:

- `scene_id`;
- `worldpack_id`;
- canonical `SceneTime`;
- canonical location;
- canonical subjects;
- canonical semantic action;
- canonical visual focus;
- canonical camera entry;
- semantic lighting/style/safety values that survived the earlier VST boundary.

This prevents Module 13 from needing hidden state to determine which world, turn, day, or phase the visual contract belongs to.

## Presence and location

Module 12 fails closed when the RAW VST contradicts observable scene truth.

A RAW VST location different from the observable location is an error.

A RAW VST subject that is not visible in `ObservableSceneState` is an error.

An action participant that is not visible or is not included in the rendered subject set is an error.

A visual-focus target that is not visible or is not included in the rendered subject set is an error.

The canonicalizer does not silently teleport an NPC, add an off-scene character, or invent a location.

The executable specification allows one controlled visual revision for bad VST output. That retry policy is intentionally not hidden inside this pure canonicalizer; it belongs to the later visual bridge/orchestration layer, where retry count and diagnostics can be controlled explicitly.

## Rendered-subject subset

The RAW VST may frame only a subset of the subjects visible in the scene. That is a composition choice, not a change to world presence.

For every selected subject, Python verifies real presence and then rebuilds the canonical subject from authoritative data.

Canonical subject ordering follows `ObservableSceneState`, never arbitrary LLM output ordering.

## Outfit correction

`VSTSubjectIntent.outfit_intent` is deliberately non-authoritative.

If the LLM proposes an outfit that differs from the current game state, Module 12 ignores the proposal and copies the exact `ObservableSubject.outfit` into `CanonicalSubject`.

Example:

```text
RAW VST: Victoria wears an invented red bikini
ObservableSceneState: Victoria wears the current white summer dress
CanonicalVST: white summer dress
```

No outfit text from the RAW VST survives into the canonical contract.

## VisualState

The current `ObservableSubject.visual_state` is deep-copied into the canonical subject.

The LLM cannot override current body/visual conditions through RAW VST semantic text.

## Visual identity

Every rendered subject must have a `CharacterVisualCanon` in the active Worldpack.

The canonicalizer takes from that definition:

- `base_prompt`;
- `role_prompt`;
- `visual_gender`;
- `canonical_traits`.

Missing visual canon is an explicit error.

These values are still semantic/canonical identity data. Stable Diffusion prompt assembly remains Module 13's responsibility.

## LoRA resolution

The LLM never chooses a LoRA filename.

For a character with `lora_alias`, Python resolves that alias through `VisualDocument.loras`.

Unknown or empty aliases fail explicitly.

The canonical contract stores both the authorized alias and resolved filename so later prompt/workflow modules do not need to reinterpret identity.

## Semantic libraries

Module 12 resolves action, pose and camera semantics through the generic Worldpack libraries.

The current Worldpack schema exposes:

```text
entry_id
description
tags
```

No alias field is invented by the engine because the current canonical schema does not define one.

User-authored library contents are not modified by this module.

### Deterministic resolution policy

Resolution is deliberately conservative:

1. exact normalized `entry_id` match when resolving one semantic intent;
2. exact normalized description match;
3. deterministic evidence score from authored tags and lexical overlap;
4. a tag overlap is valid evidence;
5. without tag evidence, at least two lexical words must overlap;
6. no candidate means explicit `no match` error;
7. equal best candidates mean explicit `ambiguous` error.

A single generic word such as `standing` is not enough to select `standing_poolside` for a different context.

`SemanticLibraryDocument` also rejects duplicate IDs after whitespace/case normalization, so `Same` and ` same ` cannot represent two independent canonical entries.

The resolver is behind `SemanticResolverProtocol`, allowing the implementation to evolve later without changing the canonicalizer contract. Any future semantic/vector implementation must remain deterministic at the Python authority boundary and must still fail closed on unresolved ambiguity.

## DEC-005 boundary

Module 12 preserves the Product Owner's current visual prompt decisions.

The canonical output does not carry dynamic negative prompt composition from:

- `CharacterVisualCanon.negative_prompt`;
- `VisualDocument.world_negative`;
- scene mood;
- NPC emotions;
- LLM-generated negative terms.

Those legacy Worldpack fields may still exist for compatibility, but they are not propagated into `CanonicalVST`.

Module 12 also has no facial-expression field and does not copy `mood_expressions` into the canonical visual contract.

Therefore psychological state is not automatically converted into facial prompt instructions.

## Determinism and isolation

For byte-identical canonical inputs, Module 12 produces byte-identical Pydantic JSON output.

Authoritative nested state is copied rather than mutated. Canonicalization does not mutate `ObservableSceneState`, `WorldState`, RAW VST, or Worldpack content.

## Failure behavior

Module 12 fails explicitly for contradictions such as:

- wrong scene ID;
- wrong Worldpack;
- wrong location;
- remote/non-visible subject;
- non-rendered action participant;
- invalid visual-focus reference;
- missing visual character canon;
- unknown LoRA alias;
- no semantic library match;
- ambiguous semantic library match.

It does not repair these contradictions by guessing.

## Explicit exclusions

Module 12 does not implement:

- Stable Diffusion positive prompt compilation;
- fixed negative prompt injection;
- prompt ordering/weight syntax;
- LoRA syntax in positive prompts;
- ComfyUI workflow mutation;
- model/checkpoint/sampler/CFG/seed selection;
- renderer calls;
- image retry/revision orchestration;
- OpenAI/Gemini provider integration;
- changes to the user's authored semantic library files.

Those responsibilities remain in later modules.

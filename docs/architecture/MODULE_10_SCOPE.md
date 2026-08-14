# Module 10 — Observable Scene State

## Status

Module 10 introduces the canonical, disclosure-safe representation of the current observable moment.
It is a pure Python application boundary: no LLM, renderer, filesystem, provider, or prompt compiler is used here.

The governing rule remains:

> The LLM interprets, reasons, and narrates. Python governs the world.

## Purpose

`ObservableSceneState` is the single scene contract shared by downstream narration, VST generation, image generation, and later memory/event integration.

It is not a summary of `WorldState` and it is not an NPC cognitive context.
It contains only facts authorized to be observable in the current moment.

The intended flow is:

```text
Authoritative WorldState
        +
already-authorized turn facts
        ↓
ObservableSceneBuilder
        ↓
ObservableSceneState
        ├─→ NarrationContext
        └─→ Module 11 Visual Director / VST
```

## Python-authoritative facts

The builder derives directly from `WorldState`:

- session and worldpack identity;
- canonical turn/day/world phase;
- player location;
- player presence;
- NPC presence by co-location with the player;
- player/NPC identity and role;
- authoritative outfit;
- authoritative `VisualState`.

Visible NPC ordering is deterministic by entity ID. The player is always the first subject.
The returned scene owns deep copies of mutable nested state.

## Already-authorized observation input

Some facts required for a visual/narrative scene do not yet exist as authoritative fields in `WorldState`, for example a fine-grained position such as `pool_edge` or a visibly expressed mood.

Those facts enter through strict `SceneObservationInput` contracts only after an upstream Python-authoritative subsystem has authorized them:

- `SceneSubjectCue.position`;
- `SceneSubjectCue.mood_expressions`;
- observable consequences;
- validated action;
- resolved Python dice check.

Module 10 does not infer or invent these facts.

## Internal emotion is not visible expression

`NPCState.emotional_state` is intentionally not copied into `ObservableSceneState`.

A high internal anger, fear, attraction, jealousy, or other emotion does not automatically mean the character visibly displays it. An NPC may suppress or mask an emotion.

Therefore:

```text
internal EmotionalState != observable mood/expression
```

Only an already-authorized `mood_expressions` cue becomes observable.

## Privacy boundary

The observable scene deliberately excludes:

- `world_truth`;
- NPC knowledge;
- NPC beliefs and false beliefs;
- NPC secrets;
- memories;
- relationship state;
- intimacy state;
- private cognitive context;
- hidden intentions unless represented by an authorized observable action/consequence.

The scene is safe to pass to downstream visual systems without exposing private game truth.

## Presence and reference integrity

The scene fails closed when observable data references a subject that is not present.

Python validates that:

- subject IDs are unique;
- exactly one player subject exists;
- action entity targets are visible;
- consequence subject IDs are visible;
- visual-focus candidate subject IDs are visible;
- authorized dialogue speakers are visible NPCs;
- dialogue targets are visible;
- resolved check skill/difficulty/rating match the validated action check;
- consequence IDs are unique.

The same invariants are implemented on the Pydantic models themselves, not only in the builder, so a scene loaded or reconstructed from JSON cannot bypass them.

## Resolved action

`ResolvedSceneAction` contains:

```text
ValidatedAction
+
optional ResolvedCheck
```

The scene never rolls dice. It only carries the exact result already produced by Python.

A resolved check is rejected if it does not match the validated action's skill, difficulty, or known skill rating.

## Visual focus candidate

Module 10 provides only a conservative `VisualFocusCandidate`.

The builder derives it from visible entity targets of the validated action with reason `action_target`.
It does not choose camera, lens, composition, framing, lighting, or Stable Diffusion language.

Those belong to later visual modules.

## Authorized dialogue and one canonical moment

The executable specification requires authorized dialogue to be part of the observable scene, while the turn pipeline needs an observable scene before narration can be generated.

Module 10 resolves this without creating two independent scene truths:

1. build the base `ObservableSceneState` with a deterministic `scene_id`;
2. pass that exact scene to the Narrator;
3. validate/audit narration through Module 08;
4. attach only authorized visible-NPC dialogue to a copy of the same scene;
5. keep the same `scene_id`, location, time, subjects, action, consequences, and focus.

`attach_authorized_dialogue()` cannot change the canonical moment.

## Narration integration

Before Module 10, Module 08 received a `CognitionScene` plus separate `action` and `resolved_check` values.
That created a theoretical possibility for the narrator scene and action result to diverge.

Module 10 removes that duplication:

```text
NarrationContext.scene = ObservableSceneState
```

`NarrationContext` no longer stores independent action/check fields.
Narration evidence for location, time, visible subjects, consequences, action, and check is derived from the canonical observable scene.

`NarrationContextBuilder` additionally checks the scene against the current authoritative `WorldState` before exposing it to the Narrator:

- session;
- worldpack;
- scene/turn identity;
- day/phase;
- location;
- exact local presence set;
- player identity/outfit/visual state;
- NPC identity/role/outfit/visual state.

Cognition remains separate because an NPC private cognitive context is intentionally not an observable scene.

## Determinism

For identical authoritative state and identical authorized observation input, `ObservableSceneBuilder` produces byte-identical Pydantic JSON output.

This property is tested explicitly.

## Failure behavior

Module 10 fails closed on contradictory observable data. It does not silently:

- teleport an NPC;
- add a remote subject;
- substitute an invented outfit;
- expose a private fact;
- accept mismatched dice results;
- accept player-authored dialogue as generated NPC dialogue;
- repair a corrupt serialized scene by guessing.

## Explicit exclusions

Module 10 does not implement:

- Visual Director LLM;
- VST schema/generation (Module 11);
- visual canonicalization (Module 12);
- Stable Diffusion positive/negative prompt compilation (Module 13);
- LoRA compilation;
- ComfyUI workflow construction (Module 14);
- ComfyUI transport/rendering (Module 15);
- full turn orchestration (Module 18);
- render retry/recovery (Module 20/24).

## Acceptance direction

Module 10 establishes the boundary required for later acceptance cases such as:

- an off-screen NPC never appears in the image contract;
- an invented outfit cannot replace authoritative wardrobe state;
- narration and VST describe the same canonical moment;
- private NPC/world knowledge cannot leak into the visual branch;
- the same scene inputs are deterministic.

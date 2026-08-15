# Module 18 — Canonical Turn Orchestrator

## Purpose

Module 18 is the single application coordinator for one EPOS NEXT turn. It connects the already-existing action, dice, psychology, relationship, bond, cognition, memory, narration, observable-scene and visual subsystems without reimplementing their rules.

Fundamental authority remains:

> The LLM interprets, reasons and narrates. Python governs the world.

The orchestrator knows **when** a subsystem is invoked. It does not own the subsystem's semantic rules.

## Canonical source pipeline

The executable specification requires:

```text
load authoritative state
interpret player input
validate
resolve optional check
checkpoint if dice rolled
resolve authoritative action
process only present NPCs
retrieve memories
derive emotions / relationships
derive bond state
generate NPC reactions
build ObservableSceneState
generate narration
generate VST
canonicalize VST
compile render prompt
validate new WorldState
atomic save
render image
store resulting memories
return TurnResult
```

The source explicitly permits persistence/render/memory ordering refinements when needed for atomicity.

## Module 18 refinement for atomicity

The implemented sequence is:

```text
AuthoritativeState snapshot
  -> recover pending exact-dice checkpoint, if any
  -> Action Interpreter
  -> validated action
  -> optional player check decision
  -> Python dice
  -> exact resumable checkpoint
  -> authoritative action resolution
  -> detached action-state projection
  -> present NPC selection
  -> Python psychology / relationship updates
  -> Python bond derivation port
  -> detached psychology projection
  -> present-NPC cognition only
       -> cognition service performs relevant memory recall
  -> validated NPC reactions
  -> reaction mutation proposal
  -> turn-number mutation
  -> detached turn projection
  -> one ObservableSceneState
  -> narration from that same scene
  -> memory derivation from disclosure-safe turn material
  -> Python active-memory-layer mutations
  -> final detached projection
  -> ONE validate + atomic state save + swap
  -> clear dice checkpoint
  -> visual pipeline from the same ObservableSceneState
  -> archive the already-derived long-term memory records
  -> internal TurnOrchestrationResult
```

Narration and memory derivation may run against the validated detached projection before commit, but neither can make a fact true. Only the final Python state transaction establishes authoritative truth.

## One authoritative transaction

`AuthoritativeStateManager.commit_many(...)` accepts multiple authority-homogeneous mutation batches while preserving one transaction:

```text
lock
  -> verify expected pre-turn state is still authoritative
  -> deepcopy once
  -> validate each batch authority
  -> apply all mutations to candidate
  -> validate complete candidate
  -> persist once
  -> swap once
```

This is required because one real turn can contain both `ENGINE_ONLY` mutations and validated `LLM_PROPOSABLE` reaction intentions. Two separate saves would create a crash boundary inside one turn.

A stale-state guard rejects a turn plan if another writer changed authoritative state while LLM work was in progress.

## Turn number versus GameTime

`AdvanceTurnMutation` increments only `turn_number` and is `ENGINE_ONLY`.

It does **not** change `day` or `world_phase`. GameTime remains separately Python-owned; dialogue does not automatically advance narrative time.

## Dice and exact crash resume

A checked action requires an explicit player decision before Python rolls.

After a roll the checkpoint persists:

- exact pre-turn state reference and fingerprint;
- original player input;
- validated action;
- check proposal;
- exact dice;
- derived outcome;
- player decision.

On resume, if authoritative state still matches, Module 18 skips both Action Interpreter and RNG. The exact action interpretation and dice are reused.

A different player input cannot replace a pending crashed dice turn.

If commit fails, the checkpoint remains. If commit succeeds, cleanup is attempted only after the state swap.

## Action resolution and no silent effects

`DefaultTurnActionResolver` implements only effects that are generic and unambiguous:

- unchecked movement -> engine-owned player-location mutation;
- player-owned outfit changes with exactly one Python-authorized canonical choice;
- NPC outfit requests remain pending until the target NPC's validated cognition response;
- declined checked action -> no checked effect.

It deliberately fails fast for:

- ambiguous player-owned semantic outfit choices, because the engine cannot choose a player action;
- movement controlled by a check result, because the engine has no universal rule mapping `critical_failure/failure/partial_success/full_success` to a location mutation.

Module 18B adds the generic NPC outfit-request policy: Python resolves canonical candidates,
the target NPC accepts/rejects/counteroffers through validated cognition, and only Python
creates the persistent outfit mutation. If no canonical candidate exists, cognition may
describe a bounded new outfit; Python assigns stable IDs, persists it in the runtime
wardrobe, and equips it before the shared scene is built. Module 18 never pretends that a
rejected authoritative action succeeded.

## Present NPC rule

Present NPC IDs are derived from authoritative player/NPC locations after action and psychology projections.

Only present NPCs are passed to cognition. Off-scene NPCs receive:

- no LLM call;
- no recall-driven cognition;
- no psychological event through the turn psychology planner;
- no new resulting memory through the turn memory coordinator.

The existing `NPCCognitionService` performs memory recall and builds the private cognitive context before reasoning.

## Psychology and relationships

The orchestrator does not map free-form intents to arbitrary relationship deltas.

`TurnPsychologicalEventPort` supplies authorized semantic events. `PythonTurnPsychologyPlanner` then uses the existing deterministic `PsychologyService` and per-NPC `PsychologyProfile` to update emotions and multidimensional relationships.

The planner rejects psychological events targeting off-scene NPCs.

## Bond derivation

The source requires bond/love to be Python-derived from multidimensional relationship state, memory/history, milestones and blockers. It does not specify universal numeric thresholds.

Therefore Module 18 requires a `BondDerivationPort` and does not invent thresholds in the orchestrator.

The resulting `BondState` is applied only through `ReplaceNPCBondStateMutation`, which is `ENGINE_ONLY`. An `LLM_PROPOSABLE` batch cannot set bond state.

## NPC reactions

Cognition results are validated by the Module 07 cognition boundary. Only an authorized `action_intent` can become persistent NPC intentions, and it enters state as an `LLM_PROPOSABLE` mutation that is validated again by the state authority layer.

The LLM still cannot mutate WorldState directly.

## One ObservableSceneState

The final detached turn projection produces exactly one `ObservableSceneState`.

That same disclosure-safe scene is used by:

- narration;
- memory derivation;
- visual rendering.

This prevents narration, memory and image generation from describing different versions of the same committed turn.

## Visual integration

`VisualTurnPipelineAdapter` connects Module 18 directly to the complete renderer-neutral Module 16 bridge:

```text
ObservableSceneState
  -> Visual Director LLM
  -> Raw VST
  -> Python Canonicalizer
  -> Canonical VST
  -> Python Prompt Compiler
  -> RenderPromptContract
  -> selected backend request builder
  -> RendererPort
  -> image
```

Backend selection remains composition-owned. Module 18 contains no Comfy graph logic, A1111 endpoint logic, LoRA syntax or Stable Diffusion prompt construction.

## Memory integration

Memory is derived exactly once per completed turn through `TurnMemoryDerivationPort`.

The derivation boundary receives `TurnMemoryDerivationContext`, which intentionally excludes authoritative `WorldState`. It contains only:

- player input;
- validated action;
- resolved check, if any;
- validated NPC reactions;
- the common `ObservableSceneState`;
- validated narration.

This allows a structured LLM/classifier implementation without exposing global world truth or unrelated NPC secrets.

Python then validates resulting records:

- NPC must be visible/present in the canonical scene;
- NPC must exist in authoritative state;
- memory turn must equal the candidate committed turn;
- duplicate IDs are rejected.

The same derived records serve two destinations:

1. `MemoryService` projects short-term/core/emotional active layers, emitted only as `ENGINE_ONLY ReplaceNPCMemoryLayersMutation` and included in the single WorldState commit;
2. after commit and rendering, the exact same records are archived through `MemoryStorePort` for semantic/vector recall.

There is no second memory derivation and no second WorldState save.

`TurnMemoryPlan` validates that its state effects contain only engine-owned NPC-memory-layer replacement mutations, so memory derivation cannot become a side channel for world, relationship, bond or location changes.

## Post-commit failure semantics

Once the authoritative state has been persisted and swapped, later failures must never make a caller repeat the completed turn.

Post-commit checkpoint cleanup, visual work and semantic-memory archival are converted into typed `PostCommitIssue` diagnostics. Known `EposError` codes are preserved; unexpected ordinary exceptions receive a `turn.post_commit.<phase>_unexpected` code.

Cancellation is not swallowed.

A renderer failure therefore cannot roll back the committed turn or trigger new dice/cognition.

## Internal result versus Module 19

Module 18 returns `TurnOrchestrationResult`, an internal technical record containing:

- committed state;
- validated action;
- check decision/result;
- checkpoint-reuse flag;
- cognition results;
- canonical scene;
- narration;
- visual result when available;
- memory archive status;
- post-commit issues.

The stable user/API-facing `TurnResult` remains the responsibility of Module 19.

## TDD evidence

The first Module 18 RED workflow was `31866577038`. It failed at collection because `AdvanceTurnMutation` did not yet exist, proving the state-transaction requirement was specified before implementation.

During implementation tests exposed and corrected several integration assumptions without weakening existing rules:

- a legacy checkpoint fixture lacked the new exact-resume fields;
- a psychology regression incorrectly expected `PRAISE` to increase trust, while the canonical Python rule increases affection/respect;
- mypy strict found an ambiguous empty-tuple mutation type and the production annotation was corrected;
- an ObservableScene memory check was corrected to use canonical `visible_subjects`;
- action audit found outfit requests and checked movement had no generic authoritative policy, so both now fail explicitly rather than being ignored or guessed.

The most recent fully completed pre-final gate passed 312 tests, Ruff and mypy strict on 132 source files. The final documented merge-candidate workflow is authoritative if later documentation-only commits change the branch head.

## Deliberate residual recovery concerns

Two recovery details are not hidden by Module 18:

1. **Checkpoint cleanup after successful commit.** A process crash between commit and checkpoint deletion can leave a checkpoint referencing the old pre-turn state. On next load the state-reference mismatch prevents reroll/replay, but automated stale-checkpoint cleanup belongs to the later recovery module.
2. **Long-term semantic archive batch atomicity.** `MemoryStorePort` currently exposes per-record `add`, so a failure during a multi-record archive can leave a partially written semantic store. Active NPC memory layers are already safely committed in WorldState; idempotent archive repair belongs to recovery/persistence hardening rather than causing the turn to rerun.

These are explicit recovery concerns, not reasons to invalidate an already committed turn.

## Handoff to Module 19

Module 19 must map `TurnOrchestrationResult` into the stable public `TurnResult` without re-running interpretation, dice, cognition, narration, memory derivation or rendering.

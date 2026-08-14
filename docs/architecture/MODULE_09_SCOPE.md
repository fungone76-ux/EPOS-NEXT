# Module 09 — Mutations & Atomic State Commit

## Scope

Module 09 owns the boundary where proposed changes become authoritative `WorldState`.
No LLM output, narration, or subsystem result may mutate the live state directly.

The required commit pipeline is implemented literally:

1. validate mutation authority;
2. deep-copy the current authoritative state;
3. apply typed mutations only to the detached copy;
4. validate the complete resulting `WorldState` plus cross-references;
5. persist the validated candidate through the async `StateStorePort`;
6. swap the manager's live state only after persistence succeeds.

`AuthoritativeStateManager` serializes commits with an `asyncio.Lock`, so two concurrent
commit attempts cannot interleave copy/apply/persist/swap phases.

## Typed mutations and authority

Mutations are a Pydantic discriminated union. Every type has its own schema and declares one of:

- `engine_only`;
- `llm_proposable`;
- `worldpack_only`.

The initial catalog is deliberately small rather than inventing a fixed number of mutation types:

- set world flag — engine only;
- set player location — engine only;
- set NPC location — engine only;
- set NPC intentions — LLM proposable, still Python-validated before commit;
- replace NPC emotional state — engine only;
- replace one NPC relationship state — engine only;
- set world phase — engine only.

Psychology and relationship deltas are not chosen here. Their dedicated Python engines remain
responsible for deriving canonical states; Module 09 only provides a typed commit vehicle.

## Complete-state validation

Before persistence the candidate is reconstructed through `WorldState.model_validate(...)` and
semantic cross-references are checked. The baseline validator ensures:

- player location exists;
- every NPC location exists;
- NPC/location/skill/mission/event dictionary keys match their embedded canonical IDs.

If validation fails, persistence is not attempted and the live state remains unchanged.

## Atomic JSON state adapter

`JsonFileStateStore` implements the existing async `StateStorePort[WorldState]`.
All blocking filesystem work is isolated with `asyncio.to_thread`.

Save behavior:

- preserve the current primary file as a last-known-good `.bak` when present;
- write JSON to a sibling temp file;
- flush and `fsync` the temp file;
- replace the target with `os.replace`;
- fsync the directory where supported;
- remove the temp file on write/replace failure and raise `PersistenceError`.

Load behavior tries the primary first and then the backup if the primary is missing or invalid.
The adapter never silently returns a corrupt state.

## Dice checkpoint and resume

Immediately after a Python dice roll, `DiceCheckpointService.save_after_roll(...)` can persist:

- the original `CheckProposal`;
- the exact `ResolvedCheck`, including pool size, exact dice, success count, and outcome;
- the player decision string supplied by the caller;
- a `StateReference` containing session, turn, and deterministic SHA-256 fingerprint of the exact
  authoritative state used for the roll.

`resume(...)` loads that checkpoint and verifies the state reference. It returns the already
resolved dice result; it performs no RNG call and has no dependency on `RandomSource`.
A checkpoint belonging to a different state snapshot is rejected explicitly.

`JsonFileCheckpointStore` persists this payload atomically through the same temp/fsync/replace
primitive and supports explicit clearing after the orchestrator has safely advanced beyond the
recovery point.

## Explicit exclusions

Module 09 does not:

- resolve player actions into domain consequences (later turn orchestration);
- decide psychology/relationship deltas;
- roll dice or choose check outcomes;
- orchestrate when a checkpoint is cleared (Module 18);
- build `ObservableSceneState` (Module 10);
- render images;
- implement a database-backed state store.

The important invariant is now available for later modules: Python establishes truth only after a
validated candidate has been durably persisted.

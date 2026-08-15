# Module 18B — Player Intent, Outfit Autonomy, Visual Continuity

Module 18B closes the explicit residual left by Module 18 before Module 19 begins.

## Canonical behavior

```text
player input
  -> ActionInterpretation
  -> Python ActionValidator
  -> canonical outfit candidates / ObservationIntent
  -> present NPC cognition
  -> validated accept / reject / counteroffer
  -> engine-owned outfit mutation
  -> one ObservableSceneState
  -> VST canonicalization
  -> deterministic prompt
  -> image
```

## Observation intent

`ObservationIntent` owns only player attention:

- subject must be present in the local scene;
- subject must be an explicit action target;
- body region is a stable semantic token;
- no WorldState mutation occurs.

The resulting `VisualFocusCandidate` carries subject, reason and region. When reason is
`player_observation`, Python makes the region authoritative over a contradictory raw VST and
selects a compatible canonical camera semantic from the Worldpack library.

## Outfit request authority

WorldState retains the canonical wardrobe catalog required to validate availability.
Semantic requests such as `sexy` are first filtered by authored outfit tags. When at least
one matching canonical outfit exists, cognition must choose from those candidates. When no
candidate exists, the target NPC may accept with a bounded `GeneratedOutfitProposal`.
Python—not the LLM—creates the outfit and item IDs, converts the proposal into canonical
`WardrobeOutfit` state, persists it in the runtime wardrobe, and equips it.

For an NPC target:

- accepted: the chosen candidate or requested item transition is applied;
- rejected: no outfit mutation occurs;
- counteroffer: may choose an existing candidate or provide a structured generated outfit;
- invented outfit/item IDs: validation still fails closed;
- structured generation: allowed only when Python found no matching candidate.

For the player, Python may apply an exact unambiguous requested outfit. When several semantic
candidates remain, the engine requires clarification rather than choosing the player's
action.

## Persistent layers

Removing an item changes that canonical item's state to `removed`; it does not delete the
item. Prompt compilation uses `visible_items()`, so removed shoes disappear while socks or
other inner layers remain. Rewearing restores visibility. The same state is persisted and
therefore affects every later scene until another authorized mutation changes it.

## Turn ordering invariant

An accepted NPC outfit mutation is projected before the single canonical
`ObservableSceneState` is built. Narration, memory derivation and rendering therefore receive
the same post-change outfit state.

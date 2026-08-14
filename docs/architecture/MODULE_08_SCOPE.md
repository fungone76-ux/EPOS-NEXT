# Module 08 — Conversation & Narration Engine

## Scope

Module 08 converts the already validated player action and authorized present-NPC reactions into
focused, player-facing conversation/narration. It does not decide what became true in the world.
Python continues to own scene eligibility, action/check outcomes, disclosure authorization, and
the material that the narrator is allowed to see.

The application flow implemented here is:

1. semantic conversation-focus classification;
2. Python validation of speaker, target, topic and narration mode;
3. construction of a disclosure-safe `NarrationContext`;
4. narration LLM proposal as typed units;
5. Python structural validation of focus priority, evidence ownership and player-agency shape;
6. semantic narration audit LLM over the safe context plus candidate prose;
7. Python validation/rejection of every reported semantic violation;
8. deterministic composition of the accepted units.

## Conversation focus

The supported modes are:

- `brief_social`;
- `direct_dialogue`;
- `focused_interaction`;
- `action`;
- `exploration`;
- `dramatic_scene`.

The engine does not classify greetings with fragile checks such as `words[0] == "buonasera"`.
`ConversationFocusService` delegates semantic classification to an `LLMPort` and Python validates
the proposal. The exact player input is preserved in the classification context, so variants such
as `buonasera`, `buona sera`, `salve Victoria`, `ciao Victoria` and `ehi Victoria!` can be handled
semantically by the provider integration without hardcoding one spelling into engine rules.

If the validated player action explicitly addresses a present NPC, the focus classifier cannot
silently switch to another NPC. For conversational modes a target NPC is required. This makes the
player's current exchange higher priority than unrelated NPC initiative.

## Narrator context isolation

`NarrationContextBuilder` is deliberately separate from Module 07's private cognitive context.
The narrator receives only:

- the exact player input;
- local observable scene data;
- validated action;
- already resolved Python check, when present;
- authorized NPC reactions;
- public voice/personality, current emotion and player relationship summaries for reacting NPCs;
- explicitly whitelisted narration evidence.

It does not receive `WorldState.world_truth`, another NPC's private state, the NPC's entire memory
archive, locked secrets, or raw chain of thought.

Ordinary NPC knowledge/beliefs/discoveries enter narration only through explicit
`NarrationKnowledgeSelection` items. A memory is not exposed merely because cognition recalled or
referenced it: the caller must additionally provide a `NarratableMemory`, and the builder verifies
that the owning NPC's authorized reaction actually references that memory ID.

An NPC secret enters narration evidence only when Module 07 has already placed that secret ID in
`authorized_secret_disclosures`. Unknown disclosure IDs are rejected.

## Evidence ownership

Every generated unit cites evidence IDs. NPC dialogue must cite that NPC's authorized reaction.
Private evidence keeps an owner ID, and one NPC cannot use another NPC's private knowledge,
beliefs, memories or authorized secrets.

World narration may use only already observable/player-declared/resolved action/check evidence.
It cannot structurally promote private NPC evidence or an uncommitted NPC action intention into
world truth. When world narration names the player as a subject, it must be grounded in the
player's own declaration or a resolved action/check result.

## Semantic narration audit

Evidence ownership alone cannot prove that unrestricted natural-language prose faithfully realizes
its evidence. A syntactically valid unit could still smuggle an unsupported sentence such as
"the player decides to follow her". Module 08 therefore does not rely on brittle keyword filters
or on the narrator grading itself implicitly.

After structural validation, `NarrationService` sends the already safe `NarrationContext` and the
candidate `ValidatedNarration` through a separate audit `LLMPort`. The audit produces only typed
semantic findings. The supported baseline violation classes are:

- `player_control`;
- `unsupported_world_claim`;
- `unauthorized_private_info`;
- `focus_violation`.

The audit LLM has no authority to approve mutations or make facts true. Python validates every
finding's unit reference. If one or more valid findings exist, Python rejects the narration before
composition. A clean audit is required; there is no production path in `NarrationService` that
silently skips this step.

This is intentionally consistent with the EPOS authority rule: the LLM interprets the semantic
meaning of prose, while Python decides whether that prose may leave the narration boundary.
Provider-specific prompts and structured-output adapters remain Module 17 concerns.

## Player agency

The narration union intentionally has only `npc_dialogue` and `world_narration` units. There is no
`player_dialogue` unit. Pydantic `extra="forbid"` rejects an invented player-dialogue structure.
The narration LLM may realize what the player already declared and external consequences already
resolved by Python; it is not given a contract for inventing a new player decision, thought or
utterance. The mandatory semantic audit adds a second guard against player-control statements that
cannot be proven by structure alone.

## Pacing

For `brief_social`, the focused target NPC must answer first, unrelated NPC dialogue is rejected,
and the default validation contract keeps the result to one or two sentences. For
`direct_dialogue` and `focused_interaction`, the target NPC must also be the first narration unit.
Other modes allow broader externally grounded narration, still subject to structural validation and
the semantic audit.

## Explicit exclusions

Module 08 does not:

- mutate or commit `WorldState` (Module 09);
- build the final post-mutation `ObservableSceneState` (Module 10);
- implement OpenAI/Gemini provider adapters or prompts (Module 17);
- decide dice/check outcomes;
- make NPC action intentions authoritative;
- persist new memories of the turn;
- render images.

The final turn orchestrator will connect these contracts to the authoritative mutation and
post-commit scene pipeline without weakening these boundaries.

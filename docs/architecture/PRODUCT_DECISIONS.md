# EPOS NEXT — Product-owner decisions frozen before implementation

## DEC-001 — Engine and Worldpacks

The engine is stable and generic. Worldpacks are interchangeable content packages.
No Resort-specific NPC, location, skill, mission, wardrobe, schedule, or narrative rule may
be hardcoded into `src/epos/`.

## DEC-002 — Canonical ComfyUI workflow

`resources/comfyui/comfy_workflow_image.json` is preserved from the proven workflow supplied
by the Product Owner. It is a baseline asset, not a prompt-generation mechanism.

SHA-256 at import into EPOS NEXT:

`ce6ffe26c500289fc737d4ef7af64125a5a7ee9de626b58650ea024d66398998`

Later visual modules may inject only explicitly authorized runtime parameters through a
validated Python workflow builder. The LLM never edits or directly drives this JSON.

## DEC-003 — Adult intimacy is separate from love and ordinary relationships

EPOS NEXT is an adult RPG. Sexual intimacy is modeled independently from trust, affection,
respect, general attraction, and emotional bond.

The engine may track NPC sexual attraction, desire, arousal, comfort, tension, and sexual
history per partner. The engine must never assign sexual desire, arousal, or preferences to
the player.

Sexual activity requires both participants to be adult-verified and requires explicit,
scoped, current consent. Numeric intimacy or relationship scores never imply consent.
Consent may be declined or withdrawn.

`BondPhase` represents only general emotional bond depth. `LovePhase`, implemented during
the final acceptance hardening, is a separate optional Python-derived field inside the
authoritative bond state and is not the primary progression axis of the adult intimacy
system. Attraction alone never sets it. Progress requires multidimensional relationship
thresholds, blockers, shared core memories, narrative time, meaningful events, and staged
advancement with hysteresis.

## DEC-004 — NPC memory has five operational levels

EPOS NEXT uses five operational memory levels: short-term, long-term semantic, core,
emotional, and consolidation capsules.

Python decides when consolidation is needed and selects the eligible source memories. Core
memories, explicitly protected memories, promises, betrayals, confessions, discovered
secrets, irreversible decisions, and relationship milestones are excluded from ordinary
compression.

An LLM may summarize only the source memories selected by Python and must return a validated
structured summary. The LLM does not choose source IDs, cannot delete raw memories, and does
not decide which memories are protected. Python creates the capsule provenance and keeps the
original archive available.

## DEC-005 — Fixed negative prompt and no facial-expression prompt layer

The Stable Diffusion/ComfyUI negative prompt is fixed. Runtime visual modules must use the
single canonical negative prompt defined by the approved render workflow/profile; they must
not dynamically append world-, character-, scene-, mood-, or LLM-generated negative terms.

The positive prompt must not contain a facial-expression layer. Runtime prompt compilation
must not add facial-expression directives such as smiles, anger, sadness, seductive
expressions, eyebrow/eye/mouth expressions, or equivalent face-emotion instructions.
Psychological emotion remains part of the game state but is not translated automatically
into facial prompt text.

## DEC-006 — Player visual attention and persistent outfit continuity

Player language may express an observation target and a body-region focus without changing
world truth. `ObservationIntent` is validated against the local scene and its region is
carried through `ObservableSceneState`. For explicit player observation, Python overrides a
contradictory Visual Director focus and resolves a compatible camera from the Worldpack
camera library.

Outfit requests directed at NPCs are requests, never completed actions. Python first exposes
canonical wardrobe candidates. The present NPC may accept, reject, or counteroffer through
a structured cognition result. If no matching outfit exists, cognition may instead return a
bounded structured outfit draft. Python generates stable IDs, validates every garment, adds
the result to the runtime wardrobe, and only then applies it as an engine-owned mutation
before the shared scene is built.

Removed items remain in authoritative outfit state with `state=removed` but are omitted from
visual prompt compilation. Other layers remain visible. This persists across turns until a
later authoritative action changes the item state or replaces the outfit.

The Visual Director therefore has no dedicated facial-expression output field. Observable
mood/expression cues are not exposed to its Module 11 context. Later canonicalization and
prompt compilation must preserve this boundary.

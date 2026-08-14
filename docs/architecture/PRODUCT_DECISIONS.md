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

`BondState` represents only general emotional bond depth. Love, if implemented later, is an
optional derived state and is not the primary progression axis of the adult intimacy system.

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

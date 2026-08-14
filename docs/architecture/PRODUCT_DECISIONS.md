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

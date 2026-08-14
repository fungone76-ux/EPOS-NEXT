# Module 16B — Resort Visual Semantic Libraries Integration

## Status and purpose

Module 16B integrates the Product Owner's authored Resort visual vocabularies into the Python-authoritative visual pipeline built in Modules 11–16.

The selected source base is `epos_visual_libraries.zip`. The alternative package was reviewed but retained only as a secondary reference because its vocabulary is substantially smaller.

The governing flow remains:

```text
Visual Director LLM
        ↓ semantic intent only
SemanticLibraryResolver (Python)
        ↓ canonical library entry
VisualCanonicalizer / Prompt Compiler (Python)
        ↓ authored positive_fragment
RenderPromptContract
```

The LLM never writes Stable Diffusion prompt fragments directly.

## Runtime libraries

The Resort Worldpack now contains seven standard visual libraries:

| Library | Runtime entries |
|---|---:|
| action | 181 |
| pose | 99 |
| camera | 43 |
| lighting | 31 |
| location_visual | 9 |
| outfit | 221 |
| style | 8 |
| **Total** | **592** |

The repository packages the current authored payloads as deterministic `*.yaml.gz` files. `FileSystemWorldpackLoader` first checks for an uncompressed `*.yaml` file and, when none exists, falls back to `*.yaml.gz`.

This precedence intentionally supports an authoring workflow in which a readable YAML file can replace/override the packaged version without changing engine code.

## Library schema

`SemanticLibraryDocument` supports strict metadata:

```yaml
schema_version: 1
library_id: action_library
description: Human-readable purpose
world_id: resort_world  # optional
entries:
  - entry_id: walking_forward
    description: subject walking forward normally
    aliases:
      - walking
      - moving forward
    tags:
      - movement
      - walking
    positive_fragment: walking forward
```

Rules enforced by Pydantic/Python:

- schema version must be supported;
- normalized `entry_id` values are unique;
- exact normalized aliases are unique across entries;
- when `library_id` is declared, it must match the Worldpack slot being loaded;
- when `world_id` is declared, it must match the active Worldpack;
- unknown/mismatched bindings fail closed.

## Deterministic cleanup of supplied data

The selected source package was cleaned mechanically rather than semantically rewritten:

- duplicate normalized outfit `entry_id` rows were merged;
- distinct aliases/tags from duplicate rows were retained;
- exact aliases owned by more than one entry were removed from all conflicting entries;
- authored `positive_fragment` content was preserved;
- no replacement visual content was invented to fill gaps.

The source outfit library contained 233 rows. After duplicate-ID consolidation the runtime library contains 221 unique entries.

## Outfit authority

`OutfitItem.visual_entry_id` is now the optional authoritative bridge between canonical wardrobe state and the outfit visual library:

```text
WorldState OutfitItem.visual_entry_id
        ↓ exact entry_id only
outfit_library
        ↓
positive_fragment
```

If `visual_entry_id` is present but unknown, prompt compilation fails closed. It never silently chooses a fuzzy substitute.

If `visual_entry_id` is absent, the previous exact `item_id`/`name`/alias lookup and structured text fallback remain available for backward compatibility.

The current Resort `victoria_jacket` remains intentionally unbound because the supplied libraries contain no exact authored equivalent. EPOS does not invent a mapping merely to make the test pass.

## Adult vocabulary isolation

The supplied source package also contains an adult-only semantic vocabulary. Module 16B validates the concept through a separate `AdultSemanticLibraryDocument` schema with `content_rating: adult_18_plus`, but that vocabulary is deliberately **not** part of `LoadedWorldpack` and is not loaded by the standard visual pipeline.

Any future use requires a dedicated Python-authoritative intimacy/consent gate. A generic Visual Director intent, high attraction value, or `VSTSafetyIntent.INTIMATE_CONTEXT` alone can never authorize it.

## Runtime verification

Integration tests load the real Resort Worldpack and verify:

- all seven library counts and metadata;
- exact alias uniqueness;
- plain YAML precedence over packaged gzip;
- rejection of a mismatched `world_id`;
- adult vocabulary isolation from `LoadedWorldpack`;
- exact `visual_entry_id` outfit binding and fail-closed behavior;
- resolution of common semantic intents such as `walking`, `standing relaxed`, `medium shot`, `golden hour`, `cinematic`, and `pool`;
- actual deterministic prompt compilation from the real Resort libraries.

The fixed negative prompt and the Product Owner's no-facial-expression prompt rule remain unchanged.

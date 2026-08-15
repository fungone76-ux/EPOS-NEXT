# Module 17B — AUTOMATIC1111 / Forge Renderer Adapter

## Purpose

Module 17B adds the renderer required by the actual EPOS NEXT local runtime while preserving ComfyUI as an interchangeable backend.

The visual authority boundary remains unchanged:

```text
ObservableSceneState
  -> Visual Director LLM
  -> RAW VST
  -> Python Canonicalizer
  -> Canonical VST
  -> Python Prompt Compiler
  -> RenderPromptContract
  -> renderer-specific request builder
  -> RendererPort
  -> image
```

The LLM still never writes a final Stable Diffusion prompt, LoRA tag, checkpoint, sampler, seed or backend payload.

## Why the bridge was generalized

The Module 16 bridge was originally typed directly on `ComfyWorkflowRequest` and carried Comfy workflow resources in `VisualPipelineResources`. That prevented a second renderer from being selected without duplicating the semantic visual pipeline.

Module 17B replaces that boundary with:

- `RenderRequestBuilderPort[RequestT]`;
- `BuiltRenderRequest[RequestT]`;
- `RenderRequestSnapshot` for JSON-safe diagnostics;
- `RendererPort[RequestT]`.

The application bridge is therefore renderer-neutral. Backend-specific construction begins only after `RenderPromptContract` exists.

## ComfyUI compatibility

`ComfyRenderRequestBuilder` adapts the existing Module 14 workflow builder to the new generic request boundary. It binds the static workflow template/profile/client id and produces:

- the original typed `ComfyWorkflowRequest` used by `ComfyUIAdapter`;
- a deterministic `RenderRequestSnapshot` used by diagnostics.

A dedicated regression test proves ComfyUI still satisfies the generalized bridge.

## A1111 / Forge runtime settings

Machine-specific values are environment-owned and never stored in a Worldpack:

```text
EPOS_RENDER_MODE=a1111
A1111_BASE_URL=<local runtime value>
A1111_CHECKPOINT=<local runtime value>
A1111_TIMEOUT_SECONDS=<optional local runtime value>
```

The repository `.env.example` contains placeholders only. The real deployment `.env`, API keys, model values, endpoint values and local paths are not committed.

`A1111AdapterSettings` validates these settings and refuses to activate when an explicitly configured `EPOS_RENDER_MODE` selects another renderer.

## Worldpack-owned A1111 policy

Worldpacks may declare visual policy, not machine configuration. Resort World declares:

```yaml
rendering_config:
  a1111:
    default_lora_weight: 0.8
    dimension_multiple: 8
    min_dimension: 64
    max_dimension: 2048
```

`A1111RenderProfile.from_rendering_config(...)` validates this section with strict Pydantic rules. Unknown fields such as `base_url`, `checkpoint` or local output paths are rejected because those values belong to the runtime environment.

## Prompt and LoRA compilation

`SemanticPromptCompiler` remains backend-neutral and returns structured `ResolvedLora` records rather than A1111 syntax.

`A1111RenderRequestBuilder` is the only layer that converts an authorized resolved LoRA into:

```text
<lora:alias:weight>
```

Weights come from `A1111RenderProfile`, never from the LLM. Aliases containing prompt-control characters such as `<`, `>`, `:` or newlines are rejected before request construction.

The fixed negative prompt and canonical positive prompt are otherwise preserved exactly from `RenderPromptContract`.

## Checkpoint authority

The checkpoint in a `RenderPromptContract` may originate from another renderer profile and is therefore not treated as A1111 runtime authority.

For A1111/Forge, `A1111_CHECKPOINT` from local runtime settings is injected through:

```json
{
  "override_settings": {
    "sd_model_checkpoint": "<runtime checkpoint>"
  },
  "override_settings_restore_afterwards": true
}
```

This changes the checkpoint for one request without intentionally changing the global renderer configuration for subsequent turns.

## HTTP boundary

`A1111HTTPClient` is fully async through `httpx` and uses the WebUI API:

- `GET /sdapi/v1/options` for health;
- `POST /sdapi/v1/txt2img` for generation.

The returned first image is strictly base64-decoded, then written through the existing atomic render image store.

Transport failures, HTTP rejections, malformed JSON and invalid base64 are classified through the existing renderer error taxonomy.

## No ambiguous POST retry

Unlike ComfyUI, txt2img is synchronous and does not return a durable server prompt id before generation. If the connection is lost after the POST is sent, the client cannot reliably know whether the image was already generated.

Therefore `A1111ForgeAdapter.render(...)` performs exactly one txt2img submission. An ambiguous transport failure returns a failed `RenderResult` with `attempts=1`; it never silently submits a duplicate image job.

Higher-level recovery may later decide whether the persisted visual contract should be rendered again.

## Deterministic request identity

Before submission, Python serializes the canonical A1111 API payload and seed deterministically and derives:

```text
a1111-<sha256 prefix>
```

This request id is stored in `RenderRequestSnapshot` and returned as `RenderResult.prompt_id`. It is an EPOS diagnostic/recovery identity, not a server-side A1111 job id.

## Diagnostics and recovery invariant

The renderer-neutral bridge still persists the prepared snapshot before contacting the renderer:

- RAW VST;
- Canonical VST;
- RenderPromptContract;
- backend name;
- deterministic request id;
- JSON-safe backend request payload.

Only then is `RendererPort.render(...)` invoked. Failure of the final diagnostics write after rendering never triggers a second renderer call.

## TDD evidence

Initial RED commits:

- `b975698455c72ae26bc7eb4d883c640120767e7f` specified the A1111/Forge adapter contract before the package existed;
- `bf8c0648185c49ade2c251669fa627e85ee2e12d` specified the renderer-neutral bridge before the new application contracts existed.

Workflow `31865162216` failed with exactly two collection errors for those missing contracts.

The first functional GREEN reached 280 passing tests. Ruff then exposed formatting only. After formatting, mypy strict exposed one variance error in the generic request-builder Protocol; the Protocol was corrected rather than weakened.

Workflow `31865689014` then passed:

- 281 tests;
- Ruff;
- mypy strict on 126 source files.

Subsequent tests add Resort A1111 policy loading, Comfy compatibility, unsafe LoRA rejection and dimension-policy validation. The final merge-candidate workflow is the authoritative quality evidence for this module.

## Handoff to Module 18

Module 18 may select one renderer composition from runtime configuration:

```text
EPOS_RENDER_MODE=a1111
  -> A1111RenderRequestBuilder
  -> A1111ForgeAdapter

EPOS_RENDER_MODE=comfyui
  -> ComfyRenderRequestBuilder
  -> ComfyUIAdapter
```

Turn orchestration must not contain A1111 endpoint logic, Comfy node logic, LoRA syntax or final prompt compilation. It should depend only on the already-composed visual pipeline and typed application contracts.

# Module 15 — ComfyUI Adapter

## Status

Module 15 implements the infrastructure adapter that submits an already validated `ComfyWorkflowRequest` to ComfyUI, observes execution to completion, downloads the final output image, atomically persists it locally, and returns a backend-neutral `RenderResult`.

The governing boundary is:

```text
ComfyWorkflowRequest
        ↓
RendererPort / ComfyUIAdapter
        ↓
ComfyUI HTTP API
        ↓
prompt_id
        ↓
history polling
        ↓
final output metadata
        ↓
image download
        ↓
atomic local save
        ↓
RenderResult
```

Module 15 does not know `WorldState`, NPC psychology, player input, RAW/Canonical VST semantics, prompt compilation rules, or game-state mutation.

## Application contracts

`epos.application.visual.rendering` contains backend-neutral renderer contracts:

- `RendererPort[RequestT]`;
- `RendererHealth`;
- `RenderResult`;
- classified renderer errors.

`RenderResult` exposes:

- `status`: `success` or `failed`;
- `image_path`;
- `backend`;
- `prompt_id` when known;
- `error` when failed;
- `duration_ms`;
- total submission `attempts`.

Successful results require both an image path and a prompt ID. Failed results require a non-empty diagnostic and never expose an image path.

## ComfyUI configuration

The adapter supports the canonical environment names:

```text
EPOS_RENDER_MODE=comfyui
EPOS_COMFYUI_ENDPOINT=http://127.0.0.1:8188
EPOS_COMFYUI_WS_ENDPOINT=ws://127.0.0.1:8188/ws
```

These values are represented by strict `ComfyUIAdapterSettings` together with explicit request timeout, render timeout, polling interval, retry delay, local output directory, and maximum total attempts.

`max_attempts` is constrained to `1..3` so retry multiplication cannot silently exceed the product requirement.

The websocket endpoint is retained in configuration for future progress support, but Module 15 intentionally uses HTTP polling for completion because the canonical specification explicitly permits websocket **or** history polling.

## Health check

`health_check()` calls ComfyUI `/system_stats` and returns `RendererHealth`.

When available, the current ComfyUI version is read from `system.comfyui_version`.

Connection/protocol failures are returned as `renderer_available=False` with the real diagnostic. They are not swallowed and they do not require any game-state access.

## HTTP protocol

The production HTTP boundary is asynchronous and uses `httpx`.

Endpoints used by this module:

```text
GET  /system_stats
POST /prompt
GET  /history/{prompt_id}
GET  /view?filename=...&subfolder=...&type=...
```

The `/prompt` body is exactly the already-built Comfy request:

```json
{
  "prompt": {"...": "validated workflow graph"},
  "client_id": "..."
}
```

The HTTP client validates that a successful `/prompt` response contains a non-empty `prompt_id`.

4xx workflow rejection is classified as execution failure. 5xx and transport failures are classified as connection failures. Invalid JSON/protocol payloads are classified separately.

The real HTTP client is exercised through `httpx.MockTransport` in CI, so endpoint paths, request body, view query parameters, response parsing, and failure classification are tested without requiring a live ComfyUI server.

## Completion strategy

The first adapter implementation uses bounded history polling.

After ComfyUI returns a `prompt_id`, the adapter polls `/history/{prompt_id}` until:

- a completed output image appears;
- Comfy reports an execution error;
- the render timeout is exceeded;
- a transport/protocol error occurs.

Only image metadata with `type == "output"` is accepted as the final image. Temporary previews are never mistaken for canonical output.

Comfy execution diagnostics preserve useful node information when provided, including node ID/type and exception details.

## Retry ownership and duplicate-job safety

Module 15 owns its submission-attempt budget; no nested 3×3 retry policy exists.

Automatic retries are limited to connection failures while submitting `/prompt`, with at most three total attempts.

A stronger invariant applies once a `prompt_id` has been observed:

> The adapter never automatically submits the workflow again after ComfyUI has returned a prompt ID.

If history polling, image download, or local persistence fails after acceptance, the failed `RenderResult` preserves that `prompt_id`. This allows later recovery logic to reason about the already accepted job rather than blindly creating a duplicate render.

Turn-level rerender/recovery policy belongs to later modules and must use persisted visual contracts rather than new LLM cognition or new game-state mutation.

## Output discovery

The history interpreter walks completed node outputs deterministically and selects only output images.

A completed job with no final output image is an explicit failure rather than a false success.

Temporary preview images are ignored even if they appear before the final output node.

## Download and local persistence

Comfy's remote `filename`, `subfolder`, and `type` are used only as `/view` query parameters.

They are never joined directly into the local filesystem path.

Local image names are derived from a sanitized `prompt_id` plus a safe file suffix. This prevents server-provided path traversal such as `../../escape.png`.

Image bytes are persisted through the engine's existing atomic-write primitive using `asyncio.to_thread`, preserving the no-blocking-I/O application boundary.

A persistence failure is converted into a failed `RenderResult` with the accepted `prompt_id`; it does not escape as an unclassified render success.

## Narrative/state authority

Renderer success or failure is non-authoritative with respect to the narrative world.

This module has no access to `WorldState` and therefore cannot roll back, mutate, or invalidate a successfully committed narrative turn.

The later visual bridge/orchestrator will decide how a failed `RenderResult` is attached to a completed turn. Module 15 only reports renderer truth and diagnostics.

## Dependency injection

The adapter depends on protocols for:

- Comfy API access;
- image persistence.

The production implementation uses `HttpxComfyApiClient` and `AtomicRenderImageStore`.

`HttpxComfyApiClient` accepts an optional `httpx.AsyncBaseTransport` solely as a test/infrastructure seam. Production leaves it unset and therefore uses normal `httpx` networking.

## Explicit exclusions

Module 15 does not implement:

- RAW VST generation;
- visual canonicalization;
- positive/negative prompt compilation;
- workflow graph construction;
- websocket progress UI;
- GUI progress display;
- turn orchestration;
- persistence of the complete visual contract;
- `Retry Image` command semantics;
- image regeneration after restart;
- renderer diagnostics database/log aggregation;
- LLM provider integration.

Those responsibilities remain in later modules.

# Module 22 — FastAPI / Debug API

`create_app(...)` exposes the shared `EPOSRuntimePort` through typed FastAPI routes:

- `POST /sessions`
- `GET /sessions/{id}`
- `POST /sessions/{id}/turns`
- `POST /sessions/{id}/advance`
- `POST /sessions/{id}/resume`
- `POST /sessions/{id}/rerender`
- `GET /worldpacks`
- `GET /health`
- `GET /health/llm`
- `GET /health/renderer`

Requests and responses use strict Pydantic contracts shared with the desktop adapter.
Missing resources become HTTP 404; classified EPOS validation/state failures become typed
400/409 responses. The API does not create an alternate turn path and cannot bypass the
canonical orchestrator, result mapper or render-recovery service.

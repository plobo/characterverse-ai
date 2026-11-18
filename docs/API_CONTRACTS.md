# API Contracts

Source of truth: [`shared/api-contracts/openapi.json`](../shared/api-contracts/openapi.json) (generated from the
FastAPI app; CI fails if it is stale). Interactive docs at `http://localhost:8000/docs`.

## Conventions
- JSON, camelCase, UTC timestamps `2026-11-17T22:41:05.123Z`.
- `Authorization: Bearer <session>` on everything except `/healthz`, `POST /v1/auth/session`, `GET /v1/assets*`,
  `GET /v1/catalog/manifest` and signed `/v1/media` / `/v1/upload` URLs.
- Ownership is enforced on every read/write; objects owned by someone else return **404**.
- Errors: `{"error": {"code", "message", "details": [{code, field, message}], "retryable"}}` — codes in
  [`error_codes.json`](../shared/api-contracts/error_codes.json). Clients retry only `retryable` codes and network
  errors, with bounded exponential backoff, and only for GETs or requests carrying an `Idempotency-Key`.
- Versioned documents: character recipe v1 and storyboard v1 (`shared/json-schemas`).

## Endpoints
| Area | Endpoints |
|---|---|
| Auth & users | `POST /v1/auth/session` · `GET/PATCH/DELETE /v1/me` · `GET /v1/me/usage` · `GET /v1/me/export` |
| Assets | `GET /v1/assets?type=` · `GET /v1/assets/{id}` · `GET /v1/assets/{id}/preview-url` · `GET /v1/catalog/manifest` |
| Characters | `GET/POST /v1/characters` · `GET/PATCH/DELETE /v1/characters/{id}` · `POST /v1/characters/generate-recipe` · `POST /v1/characters/{id}/preview` · `POST /v1/characters/{id}/duplicate` · `GET /v1/characters/{id}/versions` · `POST /v1/previews` |
| Mixer | `POST /v1/mixes/preview` · `POST /v1/mixes` · `GET /v1/mixes/{id}` |
| Stories & projects | `POST /v1/stories/generate` · `GET/POST /v1/projects` · `GET/PATCH/DELETE /v1/projects/{id}` · `POST /v1/projects/{id}/storyboard` · `PATCH /v1/projects/{id}/scenes/{sceneId}` |
| Rendering | `POST /v1/projects/{id}/renders` (header `Idempotency-Key`) · `GET /v1/renders` · `GET /v1/renders/{id}` · `POST /v1/renders/{id}/cancel` · `POST /v1/renders/{id}/retry` · `GET /v1/renders/{id}/download-url` |
| Media & moderation | `POST /v1/uploads/presign` · `PUT /v1/upload/{key}` · `GET /v1/media/{key}` · `POST /v1/moderation/check` · `POST /v1/reports` |

Additions beyond the plan's outline (documented here and implemented in both clients): `PATCH /v1/me`,
`/v1/me/usage`, `/v1/me/export`, `/v1/catalog/manifest`, `/v1/previews`, `/duplicate`, `/versions`,
`DELETE /v1/projects/{id}`, `GET /v1/renders`, `POST /v1/renders/{id}/retry` — all needed by screens the plan lists
(library duplicate, version history, storage usage, data export, render queue list/retry).

Job progress uses polling (2 s while active, 10 s idle); SSE/WebSocket deferred per plan §10.

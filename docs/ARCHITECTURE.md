# Architecture

```text
iOS (SwiftUI, Swift 6)          Android (Kotlin, Compose)
  SceneKit preview                Canvas 3D preview
  SwiftData drafts, Keychain      Room drafts, Keystore, WorkManager
          \                         /
           +------ HTTPS REST -----+         shared/: OpenAPI, JSON schemas, asset manifests,
                      |                      design tokens, golden fixtures (parity tests)
              FastAPI modular monolith
  auth · users · characters · assets · mixer · stories · projects · render · media · moderation
                      |
        PostgreSQL (SQLite locally)  ── durable job state, registry, audit
                      |
        Queue: thread (local) / Redis+RQ (staging, prod)
                      |
        Render worker: claim+lease → procedural frames / Blender (spike) → audio stems → FFmpeg MP4
                      |
        Object storage (local FS adapter / S3) ── signed, expiring URLs only
```

## Modules (backend/app)
| Module | Responsibility |
|---|---|
| `core/` | settings (production guards), DB, JWT + HMAC signing, error envelope, rate limiter, DI container |
| `domain/models.py` | ORM: users, characters (+versions, lineage), mixes, asset_registry, licences, projects, scenes, render_jobs, media_assets, moderation_events, reports, audit_events |
| `services/catalog.py` | manifest → registry seeding; licence gate (`approved`) |
| `services/recipes.py` | JSON-schema + vocabulary validation of character recipes |
| `services/assembly.py`, `drawing.py`, `previews.py` | procedural assembly → GLB + PNG, cached by recipe hash |
| `services/mixer.py` | deterministic fusion resolver |
| `services/stories.py` | storyboard validation (schema, registry, rig ↔ clip compatibility, timing) |
| `services/moderation.py` | normaliser, fuzzy deny list, imitation classifier |
| `services/ai/*` | provider interfaces + local adapters (ADR 0004) |
| `services/render.py`, `workers/*` | job lifecycle, idempotent worker, renderer, audio, queues |
| `api/*` | REST routers (OpenAPI in `shared/api-contracts/openapi.json`) |

## Procedural assembly
For a recipe: take the base model's parts; for each module, place its parts at the base model's anchor for the
module's slot (mirrored left/right when `mirrorX`, left first); then apply proportions:

* head-group parts: `p' = (c.x·W + (p.x−c.x)·K, c.y·H + (p.y−c.y)·K, c.z + (p.z−c.z)·K)`, `s' = s·K`
* other parts: `p' = (p.x·W, p.y·H, p.z)`, `s' = (s.x·W, s.y·H, s.z)`

with `H=height, W=shoulderWidth, K=headScale, c=headCenter`. Colours resolve `primary|secondary|accent|skin|#hex`.
Implemented identically in Python, Swift and Kotlin; pinned by `shared/fixtures/assembly_golden.json`.

## Fusion
Weights are normalised (left-to-right IEEE addition — Python's compensated `sum()` is deliberately avoided);
sources ranked by weight then input order. The dominant source supplies base model, rig, category and style (skeletons
are never blended). Mixed **appearance** blends proportions (`floor(x·100+0.5)/100`, clamped 0.7–1.3) and palette
(per-channel `floor(Σwᵢcᵢ+0.5)`), and pools modules in rank order filtered by licence, rig, one-per-slot and a limit
of 6. **Powers** pool by rank, filtered by rig, max 3. **Personality** pools, de-duplicated, max 5. **Voice** goes to the
strongest secondary contributor. Unmixed dimensions come from the dominant source. Omitted items are reported with a
reason (`slot_taken`, `incompatible_rig`, `unsupported_by_rig`, `limit_reached`, `not_approved`). Pinned by
`shared/fixtures/mix_golden.json` on all three platforms; clients use it for instant offline previews and the server
remains authoritative on save.

## Render job state machine
`queued → processing(preparing → rendering_scenes → composing → uploading) → completed`, or `failed` / `cancelled`.
Transient errors re-queue with backoff `min(cap, base·2^(n−1))` until `render_max_attempts`; permanent errors fail
immediately. A job is claimed with a single conditional `UPDATE … WHERE status='queued' OR lease expired`, so duplicate
deliveries and crashed workers are safe.

## Cross-platform consistency
`backend/scripts/generate_contracts.py` regenerates OpenAPI and golden fixtures; `--check` runs in CI and in
`tests/test_contracts.py`. `generate_api_samples.py` records real responses that the iOS and Android DTO tests decode.
Error codes and retry policy: `shared/api-contracts/error_codes.json`. Design tokens: `shared/design-tokens/tokens.json`.

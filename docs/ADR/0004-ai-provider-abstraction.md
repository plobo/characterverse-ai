# ADR 0004 — Provider-neutral AI abstraction

- **Status:** Accepted · **Date:** 2026-11-17

## Decision
Interfaces in `backend/app/services/ai/providers.py`: `TextGenerationProvider`, `ImageGenerationProvider`,
`SpeechGenerationProvider`, `ContentModerationProvider`, optional `EmbeddingProvider`. Each adapter exposes
`ProviderInfo` (name, version, terms URL, cost per call, typical latency, local/hosted, availability).

Default adapters are **local and deterministic** so the whole product runs offline and in CI with no paid service:
- `MockTextProvider` — structured recipe, fusion name suggestions and storyboard generation from the prompt.
- `ImitationPatternClassifier` — moderation classifier (heuristic) behind the provider interface.
- `ToneBabbleSpeechProvider` — fictional, non-impersonating "voices" synthesised from text rhythm.
- Procedural thumbnails (`render_thumbnail`) as the image provider.

**Rules:** models return structured JSON only — never code or Blender scripts; every output goes through JSON-schema
+ registry validation and a compatibility resolver; generation endpoints are rate-limited; stories are cached by
request hash and manifest version; previews are cached by recipe hash. A hosted adapter may only be enabled after
its exact licence/terms are recorded and approved in `docs/ASSET_AND_MODEL_LICENSES.md` (no hosted adapter is
enabled today).

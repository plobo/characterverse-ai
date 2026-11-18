# ADR 0005 — Asset & model licensing workflow (licence gate)

- **Status:** Accepted · **Date:** 2026-11-17

## Decision
- Every asset/model/voice/sound/music entry lives in the **asset registry** (`asset_registry` table) with
  `licence_id`, `commercial_use_approved`, provenance and SHA-256; licences live in `licences` with review status,
  reviewer and date. The version-controlled human record is `docs/ASSET_AND_MODEL_LICENSES.md`.
- An asset is usable only if **both** the registry row is approved **and** its licence is `approved` with
  commercial use. This is enforced server-side in recipe validation, mixing, storyboard validation, the public
  catalogue and preview generation; clients mirror the rule to hide unapproved items.
- Revoking a licence immediately blocks new use and previews of existing characters
  (`tests/test_licence_gate.py::test_revoking_licence_blocks_new_and_existing_use`).
- The seed manifest deliberately contains an unreviewed asset (`experimental_glow_tail_01`, `lic_pending_review`)
  to keep the gate under test.

## Review steps for a new asset
1. Record source, author, acquisition date, licence text/URL and intended use. 2. Legal/asset board review of
commercial use, attribution, redistribution and derivatives. 3. Compute SHA-256 of the exact artifact.
4. Add manifest + registry entry with a **new id/version**. 5. Pipeline validation (ADR 0002). 6. Publish.

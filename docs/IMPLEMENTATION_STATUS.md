# Implementation Status

_Last updated: 2026-11-18_

## Test summary
| Suite | Command | Result |
|---|---|---|
| Backend (unit, API, worker, real MP4 render, migrations, contracts, framing) | `cd backend && pytest` | 163 passed |
| iOS (golden parity, API decoding, view models, cache) | `xcodebuild test -scheme CharacterVerse` | 26 passed |
| Android (golden parity, API decoding, MockWebServer contract, mixer/creator logic) | `./gradlew testDebugUnitTest` | 28 passed |

The same golden fixtures (recipe validation, fusion, assembly) pass on all three platforms.

## Sprint progress
| Sprint | Status | Notes |
|---|---|---|
| 0 Technical validation | ✅ ADRs 0001–0007 · ✅ FFmpeg video/audio composition validated · ✅ licence review of all shipped assets · ⚠️ Blender headless render spike written, **not executed** (no Blender in dev env) · ⚠️ physical-device GLB/perf spike pending |
| 1 Foundation | ✅ monorepo, CI workflows, FastAPI, PostgreSQL-ready models + Alembic, auth, app shells, OpenAPI + schemas |
| 2 Asset catalogue | ✅ registry + licence gate, 6 original templates, Discover + library, 3D preview on both platforms |
| 3 Character Creator | ✅ recipe schema/validation, modular customisation, AI description → recipe, save/edit/duplicate/version |
| 4 Mixer | ✅ deterministic resolver, compatibility warnings, AI name suggestions, preview, lineage |
| 5 Story & storyboard | ✅ prompt moderation, structured script/storyboard, editing (reorder/duplicate/add/delete), persistence |
| 6 Animation Studio | ✅ environments, placement/scale, action clips per rig, camera/lighting presets, timeline, dialogue/SFX, validation |
| 7 Rendering | ✅ queue + idempotent workers, procedural renderer, audio pipeline, FFmpeg, progress, retries, cancel, export/share |
| 8 Beta readiness | ⏳ security review checklist written; accessibility labels/Dynamic Type/TalkBack semantics in place; device testing, store preparation, load tests pending |

## Acceptance criteria (plan §14.5)
| # | Criterion | Status |
|---|---|---|
| 1 | Sign in and create a profile | ✅ guest + dev providers; OIDC verifier hook (configuration pending) |
| 2 | Browse approved original templates | ✅ |
| 3 | Create and save a customised character | ✅ |
| 4 | Mix two compatible characters into a new saved character | ✅ |
| 5 | Generate and edit a short structured story | ✅ |
| 6 | Storyboard with ≥ 3 scenes | ✅ (3/4/6 scenes for 15/30/60 s; up to 8) |
| 7 | Select approved clips and environments | ✅ rig-filtered |
| 8 | Submit a render and see durable status | ✅ |
| 9 | Playable MP4 with audio | ✅ H.264/AAC verified by test (`docs/media/demo-render.mp4`) |
| 10 | Export/share the video | ✅ iOS share sheet, Android Sharesheet via FileProvider |
| 11 | All shipped assets have reviewed licence records | ✅ `docs/ASSET_AND_MODEL_LICENSES.md` (FFmpeg/Blender tooling flagged for legal review) |
| 12 | No paid pack / paid video API required | ✅ all providers local |
| 13 | iOS & Android pass the same contract + core workflow tests | ✅ shared fixtures; ⚠️ UI-automation journeys (XCUITest / Compose UI tests) not yet written |
| 14 | Delete account and data | ✅ |

## Final review (fresh reviewer) — outcome
Fixed with regression tests (`backend/tests/test_review_fixes.py`, iOS `SessionRefreshTests`, Android `SessionRefreshTest`):
refresh tokens so guest accounts survive access-token expiry and clients only sign out on auth failures; lease
sweeper for every queue backend (expired leases, cancels on dead workers, backoff honoured on restart); conditional
cancel (no cancel/claim race); RQ `--with-scheduler` for delayed retries; licence re-validation at submit and in the
worker; per-user storage prefixes removed on account deletion and renders stopped for deleted owners; streamed
upload size limit; per-client throttle on session creation; blocked moderation no longer leaves partial writes.

Deferred minors: concurrent duplicate `Idempotency-Key` race returns 500; malformed `projectId` query → 500;
`allow_dev_auth` defaults on outside production (staging must set it off); `/moderation/check` not rate-limited;
`templateId` not validated; lease renewed only on progress callbacks; no `nosniff` header on media; export omits
mixes/versions/reports; `res.body!!` in Android cache; `try!` fallback ModelContainer on iOS.

## Known gaps / next steps
- Execute the Blender worker spike in CI and benchmark against the procedural renderer.
- Replace mobile primitive viewers with RealityKit / Filament GLB playback once authored assets exist (ADR 0001).
- OIDC verifier; Redis rate limiter; S3 storage adapter; upload malware scanning.
- XCUITest + Compose UI journey tests, Room migration tests (schema v1 only today), physical-device accessibility audits.
- Real TTS provider once its terms are reviewed (current voices are fictional tone babble).
- Localised UI strings (structure ready; English only today).

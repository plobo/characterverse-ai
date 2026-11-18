# ADR 0001 — Mobile 3D preview viewer

- **Status:** Accepted (MVP) · revisit when authored GLB assets ship
- **Date:** 2026-11-17

## Context
The plan (§5.2, §11.2, §12.2) asks for a lightweight 3D preview on both platforms with validated parity, and warns
against embedding a full game engine in the MVP. There are no artist-authored, rigged GLB assets yet: the MVP
character library is procedural (ADR 0002).

## Options considered
| Option | iOS | Android | Notes |
|---|---|---|---|
| A. Native viewers over a shared primitive spec | SceneKit | Compose Canvas software renderer | No new deps; trivially identical inputs; limited realism |
| B. RealityKit + Filament loading GLB | RealityKit `ModelEntity` | Filament + gltfio | Best long-term; needs compiled materials (matc), larger APK, GLB assets that do not exist yet |
| C. Unity/Godot embedded | — | — | Rejected for MVP (size, build complexity, two runtimes) |

## Decision
**Option A for the MVP**, with Option B as the target once GLB assets exist.
- Both clients consume `shared/asset-manifests/procedural_parts_v1.json` and run the *same* assembly algorithm
  (`PartAssembler`), pinned by `shared/fixtures/assembly_golden.json` and tested on backend, iOS and Android.
- iOS renders the parts with **SceneKit** (`CharacterSceneView`, PBR materials, orbit camera, Reduce Motion aware).
  RealityKit was evaluated: the non-AR `RealityView` virtual camera requires iOS 18 and the simulator path on Intel
  Macs is unreliable; SceneKit is soft-deprecated, so the migration path is tracked here.
- Android renders the parts with a **Compose Canvas software 3D renderer** (Y-rotation, depth sort, radial shading).
  Filament is the planned replacement for GLB playback.
- The backend emits a real **GLB** for every recipe (`/v1/previews`), so the asset interchange format (glTF 2.0) is
  already exercised end-to-end and validated by tests (`glTF` magic, content type).

## Consequences
- Identical geometry inputs on all platforms today; visual fidelity differs (lighting model).
- Swapping to RealityKit/Filament is a viewer-only change: recipes, parts and APIs stay the same.
- Device spike still required on physical hardware (performance of SceneKit on low-end iPhones, Canvas on low-end Android).

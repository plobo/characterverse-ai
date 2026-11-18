# ADR 0002 — Character asset standard (glTF 2.0 / GLB) and procedural MVP library

- **Status:** Accepted · **Date:** 2026-11-17

## Decision
1. **Interchange format:** glTF 2.0 binary (GLB), y-up, metres, +z facing camera, PBR metallic-roughness materials.
2. **Rig families:** `humanoid_v1`, `critter_v1`, `mech_v1`, `creature_v1`. Skeletons are never blended (plan §6.3);
   modules, powers and animation clips declare the rigs they support.
3. **MVP library is procedural:** each base model and module is a list of primitives (sphere, capsule, box, cylinder,
   cone) with anchors per slot (`shared/asset-manifests/procedural_parts_v1.json`). Recipes are applied
   deterministically: `assemble_parts` → resolved parts → GLB + thumbnail. This is original, team-authored content
   with no third-party licence risk.
4. **Validation gates (pipeline step 9 in plan §6.4):** registry entry with licence + SHA-256 of the canonical
   definition; schema checks on parts; golden assembly fixtures; GLB structural test (header, accessors with min/max).
5. **Immutable versions:** registry rows are never mutated after publish; a new asset version gets a new id
   (`…_02`). The manifest has `manifestVersion`; recipes carry `assetManifestVersion`.

## Consequences
- Artists can later replace a procedural base with an authored GLB under the same id+rig without changing recipes.
- Animation names (`idle`, `walk`, …) are fixed identifiers shared by storyboard JSON, clients and render workers.

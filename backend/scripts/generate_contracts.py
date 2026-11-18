"""Regenerate shared contract artifacts from the Python reference implementation.

  python -m scripts.generate_contracts          # write files
  python -m scripts.generate_contracts --check  # fail if committed files are stale (used in CI/tests)

Outputs (consumed by iOS + Android tests for cross-platform parity):
  shared/api-contracts/openapi.json
  shared/fixtures/recipe_validation_cases.json
  shared/fixtures/mix_golden.json
  shared/fixtures/assembly_golden.json
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

from app.core.config import REPO_ROOT, Settings
from app.services.assembly import assemble_parts
from app.services.catalog import Catalog
from app.services.mixer import resolve_mix
from app.services.recipes import recipe_issues

SHARED = REPO_ROOT / "shared"


def _template(cat: Catalog, tid: str) -> dict:
    return copy.deepcopy(cat.get(tid).data["recipe"])


def recipe_cases(cat: Catalog) -> list[dict]:
    base = "tmpl_voltwood_guardian"
    mutations = [
        ("valid_template", lambda r: None),
        ("schema_version", lambda r: r.update(schemaVersion=2)),
        ("height_out_of_range", lambda r: r["proportions"].update(height=1.9)),
        ("bad_hex", lambda r: r["palette"].update(primary="blue")),
        ("too_many_powers", lambda r: r.update(powers=["electricity", "ice", "flight", "force_field"])),
        ("empty_name", lambda r: r.update(name="")),
        ("unknown_base", lambda r: r.update(baseModelId="humanoid_base_99")),
        ("unknown_module", lambda r: r.update(modules=["laser_sword_01"])),
        (
            "unapproved_module",
            lambda r: r.update(
                baseModelId="creature_base_01", category="creature", modules=["experimental_glow_tail_01"], powers=[]
            ),
        ),
        ("unknown_category", lambda r: r.update(category="wizardly")),
        ("category_not_supported", lambda r: r.update(category="robot")),
        ("incompatible_module", lambda r: r.update(modules=["spike_tail_01"])),
        ("slot_conflict", lambda r: r.update(modules=["leaf_cape_01", "jet_pack_01"])),
        ("unsupported_power", lambda r: r.update(powers=["fire_breath"])),
        ("unknown_trait", lambda r: r.update(personalityTraits=["sneaky"])),
        ("unknown_voice", lambda r: r.update(voiceProfileId="voice_unknown_01")),
        ("manifest_mismatch", lambda r: r.update(assetManifestVersion="0.9")),
    ]
    out = []
    for name, mutate in mutations:
        recipe = _template(cat, base)
        mutate(recipe)
        codes = sorted({i.code for i in recipe_issues(recipe, cat, SHARED)})
        out.append({"name": name, "recipe": recipe, "expectedCodes": codes})
    return out


def mix_cases(cat: Catalog) -> list[dict]:
    specs = [
        ("equal_appearance", ["tmpl_voltwood_guardian", "tmpl_nova_sprocket"], None, ["appearance"]),
        ("weighted_all_cross_rig", ["tmpl_mossy_pip", "tmpl_ember_ridgeback"], [1, 3], ["all"]),
        (
            "three_way_powers_personality",
            ["tmpl_voltwood_guardian", "tmpl_zibba", "tmpl_grimble"],
            None,
            ["powers", "personality"],
        ),
        ("voice_only", ["tmpl_nova_sprocket", "tmpl_zibba"], [2, 1], ["voice"]),
        ("uneven_palette", ["tmpl_grimble", "tmpl_zibba"], [0.7, 0.3], ["appearance", "personality"]),
    ]
    out = []
    for name, tids, weights, dims in specs:
        sources = [{"id": f"src_{i}", "recipe": _template(cat, t)} for i, t in enumerate(tids)]
        w = {f"src_{i}": x for i, x in enumerate(weights)} if weights else None
        res = resolve_mix(sources, w, dims, cat)
        out.append(
            {
                "name": name,
                "sources": sources,
                "weights": w,
                "dimensions": dims,
                "expected": {
                    "recipe": res["recipe"],
                    "omitted": res["omitted"],
                    "lineage": res["lineage"],
                    "dominantSourceId": res["dominantSourceId"],
                    "warningCodes": [x["code"] for x in res["warnings"]],
                },
            }
        )
    return out


def assembly_cases(cat: Catalog) -> list[dict]:
    out = []
    for t in cat.manifest["characterTemplates"]:
        recipe = t["recipe"]
        out.append({"templateId": t["id"], "recipe": recipe, "parts": assemble_parts(recipe, cat)})
    return out


def openapi() -> dict:
    from app.main import create_app

    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(
            env="test",
            database_url=f"sqlite:///{tmp}/c.db",
            storage_dir=Path(tmp) / "s",
            work_dir=Path(tmp) / "w",
            queue_backend="inline",
        )
        return create_app(settings).openapi()


def main() -> int:
    check = "--check" in sys.argv
    cat = Catalog.from_manifest_files(SHARED)
    outputs = {
        SHARED / "api-contracts" / "openapi.json": openapi(),
        SHARED / "fixtures" / "recipe_validation_cases.json": {"version": 1, "cases": recipe_cases(cat)},
        SHARED / "fixtures" / "mix_golden.json": {"version": 1, "cases": mix_cases(cat)},
        SHARED / "fixtures" / "assembly_golden.json": {"version": 1, "tolerance": 1e-9, "cases": assembly_cases(cat)},
    }
    stale = []
    for path, data in outputs.items():
        text = json.dumps(data, indent=2, sort_keys=False) + "\n"
        if check:
            if not path.exists() or path.read_text() != text:
                stale.append(str(path.relative_to(REPO_ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    if stale:
        print("Stale contract files (run python -m scripts.generate_contracts):\n  " + "\n  ".join(stale))
        return 1
    print("contracts up to date" if check else "contracts written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

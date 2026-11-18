from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.services.mixer import resolve_mix
from app.services.recipes import recipe_issues
from tests.conftest import create_character, template_recipe


def src(container, *template_ids):
    return [{"id": f"c{i}", "recipe": template_recipe(container, t)} for i, t in enumerate(template_ids)]


def test_equal_weight_appearance_blend(container):
    out = resolve_mix(
        src(container, "tmpl_voltwood_guardian", "tmpl_nova_sprocket"), None, ["appearance"], container.catalog
    )
    r = out["recipe"]
    assert out["dominantSourceId"] == "c0"  # tie -> input order
    assert r["baseModelId"] == "humanoid_base_01"
    assert r["proportions"] == {"height": 1.02, "shoulderWidth": 1.09, "headScale": 1.05}
    # (0x24+0xE4)/2 = 0x84, (0x5A+0x57)/2 = 88.5 -> 89 (half up), (0x75+0x2E)/2 = 81.5 -> 82
    assert r["palette"]["primary"] == "#845952"
    # rank order pool: shoulders, cape, bracers (c0) then visor, jet pack (back slot taken), tread boots
    assert r["modules"] == [
        "original_armor_shoulders_02",
        "leaf_cape_01",
        "energy_bracers_03",
        "star_visor_01",
        "tread_boots_01",
    ]
    assert {"id": "jet_pack_01", "kind": "module", "reason": "slot_taken"} in out["omitted"]
    assert r["powers"] == ["electricity", "plant_growth"]  # powers not mixed -> dominant's
    assert r["name"] == "Voltwood Sprocket"
    assert recipe_issues(r, container.catalog, container.settings.shared_dir) == []


def test_weights_pick_dominant_and_rig_rules(container):
    sources = src(container, "tmpl_mossy_pip", "tmpl_ember_ridgeback")
    out = resolve_mix(sources, {"c0": 1, "c1": 3}, ["all"], container.catalog)
    r = out["recipe"]
    assert out["dominantSourceId"] == "c1"
    assert r["baseModelId"] == "creature_base_01" and r["category"] == "creature"
    assert {"id": "leaf_cape_01", "kind": "module", "reason": "incompatible_rig"} in out["omitted"]
    assert r["powers"] == ["fire_breath", "sonic_roar", "plant_growth"]
    assert r["voiceProfileId"] == "voice_fictional_squeaky_05"  # voice from rank-1 contributor
    assert {w["code"] for w in out["warnings"]} >= {"RIG_MISMATCH"}
    assert [li["weight"] for li in out["lineage"]] == [0.25, 0.75]
    assert recipe_issues(r, container.catalog, container.settings.shared_dir) == []


def test_power_limit_and_three_sources(container):
    sources = src(container, "tmpl_voltwood_guardian", "tmpl_zibba", "tmpl_grimble")
    out = resolve_mix(sources, None, ["powers", "personality"], container.catalog)
    assert out["recipe"]["powers"] == ["electricity", "plant_growth", "time_slow"]
    assert {"id": "shape_shift", "kind": "power", "reason": "limit_reached"} in out["omitted"]
    assert len(out["recipe"]["personalityTraits"]) == 5


@pytest.mark.parametrize("weights,dims,n", [(None, ["all"], 1), ({"c0": 0, "c1": 0}, ["all"], 2), (None, [], 2)])
def test_invalid_mix_inputs(container, weights, dims, n):
    sources = src(container, "tmpl_voltwood_guardian", "tmpl_nova_sprocket")[:n]
    with pytest.raises(AppError) as e:
        resolve_mix(sources, weights, dims, container.catalog)
    assert e.value.code == "MIX_INVALID"


def test_mix_api_saves_lineage(client, auth, container):
    a = create_character(client, auth, template_recipe(container, "tmpl_voltwood_guardian"))
    b = create_character(client, auth, template_recipe(container, "tmpl_zibba"))
    body = {
        "sourceCharacterIds": [a["id"], b["id"]],
        "dimensions": ["appearance", "powers"],
        "weights": {a["id"]: 0.6, b["id"]: 0.4},
    }
    preview = client.post("/v1/mixes/preview", json=body, headers=auth)
    assert preview.status_code == 200, preview.text
    assert len(preview.json()["suggestions"]) == 3
    saved = client.post("/v1/mixes", json=body, headers=auth)
    assert saved.status_code == 201
    char = saved.json()["character"]
    assert {li["sourceCharacterId"] for li in char["lineage"]} == {a["id"], b["id"]}
    assert char["recipe"] == preview.json()["recipe"]
    fetched = client.get(f"/v1/mixes/{saved.json()['id']}", headers=auth).json()
    assert fetched["character"]["id"] == char["id"]

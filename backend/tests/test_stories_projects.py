from __future__ import annotations

import copy

from tests.conftest import create_character, sign_in, template_recipe


def make_cast(client, auth, container):
    a = create_character(client, auth, template_recipe(container, "tmpl_voltwood_guardian"))
    b = create_character(client, auth, template_recipe(container, "tmpl_mossy_pip"))
    return a, b


def generate(client, auth, ids, **kw):
    body = {
        "prompt": "find the glowing map in the crystal forest",
        "characterIds": ids,
        "durationSeconds": 30,
        "tone": "playful",
        **kw,
    }
    r = client.post("/v1/stories/generate", json=body, headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def test_generate_structured_storyboard(client, auth, container):
    a, b = make_cast(client, auth, container)
    out = generate(client, auth, [a["id"], b["id"]])
    sb = out["storyboard"]
    assert len(sb["scenes"]) == 4 and sb["scenes"][0]["environmentId"] == "env_crystal_forest_01"
    assert sum(s["durationMs"] for s in sb["scenes"]) == 30000
    for scene in sb["scenes"]:
        for sc in scene["characters"]:
            clip = container.catalog.get(sc["actionId"], "animation_clip")
            rig = "critter_v1" if sc["characterId"] == b["id"] else "humanoid_v1"
            assert rig in clip.data["rigs"]
    assert out["cached"] is False
    assert generate(client, auth, [a["id"], b["id"]])["cached"] is True


def test_story_prompt_moderated(client, auth, container):
    a, _ = make_cast(client, auth, container)
    r = client.post(
        "/v1/stories/generate",
        headers=auth,
        json={"prompt": "Captain Starlance saves the city", "characterIds": [a["id"]]},
    )
    assert r.json()["error"]["code"] == "MODERATION_BLOCKED"


def test_project_storyboard_edit_flow(client, auth, container):
    a, b = make_cast(client, auth, container)
    sb = generate(client, auth, [a["id"], b["id"]], durationSeconds=15)["storyboard"]
    p = client.post("/v1/projects", json={"title": "Map Day", "storyboard": sb}, headers=auth).json()
    assert p["version"] == 2 and len(p["storyboard"]["scenes"]) == 3
    sid = p["storyboard"]["scenes"][1]["sceneId"]
    r = client.patch(
        f"/v1/projects/{p['id']}/scenes/{sid}",
        headers=auth,
        json={
            "environmentId": "env_moon_base_01",
            "dialogue": [{"characterId": a["id"], "line": "To the moon!", "startMs": 100}],
        },
    )
    assert r.status_code == 200, r.text
    scene = r.json()["storyboard"]["scenes"][1]
    assert scene["environmentId"] == "env_moon_base_01" and scene["dialogue"][0]["line"] == "To the moon!"
    # reorder + add a scene via full replace
    doc = r.json()["storyboard"]
    extra = copy.deepcopy(doc["scenes"][0])
    extra.update(sceneId="scene_x", durationMs=2000, dialogue=[])
    doc["scenes"] = [doc["scenes"][2], doc["scenes"][0], doc["scenes"][1]]
    for i, s in enumerate(doc["scenes"]):
        s["sequence"] = i + 1
    ok = client.post(f"/v1/projects/{p['id']}/storyboard", json={"storyboard": doc}, headers=auth)
    assert ok.status_code == 200
    doc["scenes"].append({**extra, "sequence": 4})
    too_long = client.post(f"/v1/projects/{p['id']}/storyboard", json={"storyboard": doc}, headers=auth)
    assert too_long.status_code == 422
    assert too_long.json()["error"]["details"][0]["code"] == "DURATION_EXCEEDED"
    assert [x["id"] for x in client.get("/v1/projects", headers=auth).json()["items"]] == [p["id"]]


def test_storyboard_rejects_bad_assets_and_foreign_characters(client, auth, container):
    a, b = make_cast(client, auth, container)
    sb = generate(client, auth, [a["id"], b["id"]], durationSeconds=15)["storyboard"]
    p = client.post("/v1/projects", json={"title": "T"}, headers=auth).json()
    bad = copy.deepcopy(sb)
    bad["scenes"][0]["environmentId"] = "env_famous_castle"
    bad["scenes"][0]["characters"][1]["actionId"] = "wave"  # critter rig cannot wave
    r = client.post(f"/v1/projects/{p['id']}/storyboard", json={"storyboard": bad}, headers=auth)
    codes = {d["code"] for d in r.json()["error"]["details"]}
    assert codes == {"UNKNOWN_ASSET", "UNSUPPORTED_ACTION"}
    other = sign_in(client, "eve", "Eve")
    p2 = client.post("/v1/projects", json={"title": "T"}, headers=other).json()
    r = client.post(f"/v1/projects/{p2['id']}/storyboard", json={"storyboard": sb}, headers=other)
    assert "UNKNOWN_CHARACTER" in {d["code"] for d in r.json()["error"]["details"]}

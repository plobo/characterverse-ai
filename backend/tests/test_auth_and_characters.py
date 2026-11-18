from __future__ import annotations

from tests.conftest import create_character, sign_in, template_recipe


def test_endpoints_require_auth(client):
    for method, path in [
        ("get", "/v1/me"),
        ("get", "/v1/characters"),
        ("post", "/v1/projects"),
        ("get", "/v1/renders"),
        ("post", "/v1/mixes/preview"),
    ]:
        r = getattr(client, method)(path, json={}) if method == "post" else getattr(client, method)(path)
        assert r.status_code == 401, path
        assert r.json()["error"]["code"] == "AUTH_REQUIRED"


def test_public_endpoints(client):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/v1/assets?type=character-template").status_code == 200


def test_bad_token_rejected(client):
    r = client.get("/v1/me", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "AUTH_INVALID"


def test_sign_in_is_stable_and_profile_updates(client):
    h1 = sign_in(client, "bob", "Bob")
    me = client.get("/v1/me", headers=h1).json()
    h2 = sign_in(client, "bob", "Bob")
    assert client.get("/v1/me", headers=h2).json()["id"] == me["id"]
    r = client.patch("/v1/me", json={"displayName": "Bobby", "preferences": {"reducedMotion": True}}, headers=h1)
    assert r.json()["displayName"] == "Bobby" and r.json()["preferences"]["reducedMotion"] is True


def test_guest_session(client):
    r = client.post("/v1/auth/session", json={"provider": "guest"})
    assert r.status_code == 200 and r.json()["user"]["isGuest"] is True


def test_dev_auth_disabled_when_configured(client, container):
    container.settings.allow_dev_auth = False
    r = client.post("/v1/auth/session", json={"provider": "dev", "token": "x"})
    assert r.status_code == 401


def test_character_crud_versions_duplicate(client, auth, container):
    recipe = template_recipe(container, "tmpl_voltwood_guardian")
    c = create_character(client, auth, recipe)
    assert c["version"] == 1 and c["recipe"]["palette"]["primary"] == "#245A75"
    recipe["palette"]["primary"] = "#112233"
    u = client.patch(f"/v1/characters/{c['id']}", json={"recipe": recipe, "expectedVersion": 1}, headers=auth).json()
    assert u["version"] == 2
    stale = client.patch(f"/v1/characters/{c['id']}", json={"isFavorite": True, "expectedVersion": 1}, headers=auth)
    assert stale.status_code == 409
    versions = client.get(f"/v1/characters/{c['id']}/versions", headers=auth).json()["items"]
    assert [v["version"] for v in versions] == [2, 1]
    dup = client.post(f"/v1/characters/{c['id']}/duplicate", headers=auth).json()
    assert dup["name"] == "Voltwood Guardian Copy"
    client.patch(f"/v1/characters/{dup['id']}", json={"archived": True}, headers=auth)
    names = [x["name"] for x in client.get("/v1/characters?sort=name", headers=auth).json()["items"]]
    assert names == ["Voltwood Guardian"]
    all_names = client.get("/v1/characters?includeArchived=true&search=copy", headers=auth).json()["items"]
    assert len(all_names) == 1
    assert client.delete(f"/v1/characters/{c['id']}", headers=auth).status_code == 204
    assert client.get(f"/v1/characters/{c['id']}", headers=auth).status_code == 404


def test_ownership_enforced(client, auth, container):
    c = create_character(client, auth, template_recipe(container, "tmpl_mossy_pip"))
    mallory = sign_in(client, "mallory", "Mallory")
    assert client.get(f"/v1/characters/{c['id']}", headers=mallory).status_code == 404
    assert client.patch(f"/v1/characters/{c['id']}", json={"archived": True}, headers=mallory).status_code == 404
    assert client.delete(f"/v1/characters/{c['id']}", headers=mallory).status_code == 404
    assert client.get("/v1/characters", headers=mallory).json()["items"] == []
    r = client.post(
        "/v1/mixes/preview", headers=mallory, json={"sourceCharacterIds": [c["id"], c["id"]], "dimensions": ["all"]}
    )
    assert r.status_code == 404


def test_generate_recipe_from_description(client, auth):
    r = client.post(
        "/v1/characters/generate-recipe",
        headers=auth,
        json={"description": "A tall brave robot with a blue shell, gold visor, jetpack and a lightning shield"},
    )
    assert r.status_code == 200, r.text
    recipe = r.json()["recipe"]
    assert recipe["category"] == "robot" and recipe["baseModelId"] == "mech_base_01"
    assert "star_visor_01" in recipe["modules"] and "jet_pack_01" in recipe["modules"]
    assert set(recipe["powers"]) >= {"electricity", "force_field"}
    assert r.json()["provider"]["local"] is True


def test_generate_recipe_drops_incompatible_parts(client, auth):
    r = client.post(
        "/v1/characters/generate-recipe",
        headers=auth,
        json={"description": "a cute critter with a tail and fire", "category": "robot"},
    )
    body = r.json()
    assert r.status_code == 200
    assert "spike_tail_01" not in body["recipe"]["modules"]
    assert {w["code"] for w in body["warnings"]} == {"MODULE_DROPPED", "POWER_DROPPED"}


def test_preview_is_cached_by_recipe_hash(client, auth, container):
    recipe = template_recipe(container, "tmpl_nova_sprocket")
    first = client.post("/v1/previews", json={"recipe": recipe}, headers=auth).json()
    second = client.post("/v1/previews", json={"recipe": recipe}, headers=auth).json()
    assert first["cached"] is False and second["cached"] is True
    assert first["recipeHash"] == second["recipeHash"]
    glb = client.get(first["glbUrl"].replace("http://localhost:8000", ""))
    assert glb.status_code == 200 and glb.content[:4] == b"glTF"
    assert glb.headers["content-type"] == "model/gltf-binary"
    png = client.get(first["thumbnailUrl"].replace("http://localhost:8000", ""))
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_rate_limit(client, auth, container):
    container.settings.rate_limit_generate_per_minute = 2
    for _ in range(2):
        assert (
            client.post("/v1/characters/generate-recipe", headers=auth, json={"description": "hero"}).status_code == 200
        )
    r = client.post("/v1/characters/generate-recipe", headers=auth, json={"description": "hero"})
    assert r.status_code == 429 and r.json()["error"]["retryable"] is True

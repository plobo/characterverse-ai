from __future__ import annotations

from app.domain.models import AssetRegistryEntry, Licence
from tests.conftest import template_recipe


def test_registry_seeded_with_licence_and_hash(container):
    with container.db.session() as s:
        rows = s.query(AssetRegistryEntry).all()
        assert len(rows) == len(container.catalog.assets)
        for row in rows:
            assert len(row.sha256) == 64
            assert s.get(Licence, row.licence_id) is not None


def test_unapproved_assets_hidden_from_catalogue(client):
    ids = {a["id"] for a in client.get("/v1/assets?type=module").json()["items"]}
    assert "leaf_cape_01" in ids
    assert "experimental_glow_tail_01" not in ids
    assert client.get("/v1/assets/experimental_glow_tail_01").status_code == 404
    manifest = client.get("/v1/catalog/manifest").json()["manifest"]
    assert all(m["id"] != "experimental_glow_tail_01" for m in manifest["modules"])


def test_revoking_licence_blocks_new_and_existing_use(client, auth, container):
    recipe = template_recipe(container, "tmpl_voltwood_guardian")
    char = client.post("/v1/characters", json={"recipe": recipe}, headers=auth).json()
    with container.db.session() as s:
        s.get(Licence, "lic_cv_original_v1").review_status = "revoked"
        s.commit()
        container.catalog.refresh_from_db(s)
    r = client.post("/v1/characters", json={"recipe": recipe}, headers=auth)
    assert r.status_code == 422 and r.json()["error"]["details"][0]["code"] == "ASSET_NOT_APPROVED"
    assert client.post(f"/v1/characters/{char['id']}/preview", headers=auth).status_code == 422
    assert client.get("/v1/assets").json()["items"] == []


def test_asset_detail_includes_licence(client):
    body = client.get("/v1/assets/humanoid_base_01").json()
    assert body["licence"]["commercialUse"] is True
    assert body["licence"]["reviewStatus"] == "approved"

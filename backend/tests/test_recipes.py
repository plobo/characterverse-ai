from __future__ import annotations

import copy

import pytest

from app.services.recipes import recipe_issues
from tests.conftest import template_recipe


def codes(container, recipe):
    return {i.code for i in recipe_issues(recipe, container.catalog, container.settings.shared_dir)}


def test_all_templates_are_valid(container):
    for t in container.catalog.manifest["characterTemplates"]:
        assert codes(container, t["recipe"]) == set(), t["id"]


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda r: r.update(schemaVersion=2), "SCHEMA_VIOLATION"),
        (lambda r: r["proportions"].update(height=1.9), "SCHEMA_VIOLATION"),
        (lambda r: r["palette"].update(primary="blue"), "SCHEMA_VIOLATION"),
        (lambda r: r.update(modules=["leaf_cape_01"] * 2), "SCHEMA_VIOLATION"),
        (lambda r: r.update(extra="x"), "SCHEMA_VIOLATION"),
        (lambda r: r.update(baseModelId="humanoid_base_99"), "UNKNOWN_ASSET"),
        (lambda r: r.update(modules=["laser_sword_01"]), "UNKNOWN_ASSET"),
        (lambda r: r.update(category="wizardly"), "UNKNOWN_CATEGORY"),
        (lambda r: r.update(category="robot"), "CATEGORY_NOT_SUPPORTED"),
        (lambda r: r.update(modules=["spike_tail_01"]), "INCOMPATIBLE_MODULE"),
        (lambda r: r.update(modules=["leaf_cape_01", "jet_pack_01"]), "SLOT_CONFLICT"),
        (lambda r: r.update(powers=["fire_breath"]), "UNSUPPORTED_POWER"),
        (lambda r: r.update(personalityTraits=["sneaky"]), "UNKNOWN_TRAIT"),
        (lambda r: r.update(voiceProfileId="voice_celebrity_01"), "UNKNOWN_ASSET"),
        (lambda r: r.update(assetManifestVersion="0.9"), "MANIFEST_VERSION_MISMATCH"),
    ],
)
def test_invalid_recipes_report_codes(container, mutate, expected):
    recipe = copy.deepcopy(template_recipe(container, "tmpl_voltwood_guardian"))
    mutate(recipe)
    assert expected in codes(container, recipe)


def test_unapproved_licence_is_rejected(container):
    recipe = copy.deepcopy(template_recipe(container, "tmpl_ember_ridgeback"))
    recipe["modules"] = ["experimental_glow_tail_01"]
    assert codes(container, recipe) == {"ASSET_NOT_APPROVED"}


def test_create_character_rejects_invalid_recipe(client, auth, container):
    recipe = template_recipe(container, "tmpl_voltwood_guardian")
    recipe["modules"] = ["spike_tail_01"]
    r = client.post("/v1/characters", json={"recipe": recipe}, headers=auth)
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "RECIPE_INVALID"
    assert body["details"][0]["code"] == "INCOMPATIBLE_MODULE"
    assert body["retryable"] is False

"""Character recipe validation: JSON schema first, then registry vocabulary + licence gate (plan §6.2)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from app.core.errors import AppError
from app.services.catalog import Catalog, load_json

MAX_MODULES = 6
MAX_POWERS = 3
MAX_TRAITS = 5


@dataclass(frozen=True)
class Issue:
    code: str
    field: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "field": self.field, "message": self.message}


@lru_cache(maxsize=4)
def _schema_validator(path: str) -> Draft202012Validator:
    return Draft202012Validator(load_json(Path(path)))


def recipe_validator(shared_dir: Path) -> Draft202012Validator:
    return _schema_validator(str(shared_dir / "json-schemas" / "character_recipe.v1.schema.json"))


def recipe_issues(recipe: Any, catalog: Catalog, shared_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    for err in sorted(recipe_validator(shared_dir).iter_errors(recipe), key=lambda e: list(e.path)):
        issues.append(Issue("SCHEMA_VIOLATION", "/".join(str(p) for p in err.path) or "$", err.message))
    if issues or not isinstance(recipe, dict):
        return issues

    if recipe["category"] not in catalog.categories:
        issues.append(Issue("UNKNOWN_CATEGORY", "category", f"Unknown category {recipe['category']!r}"))
    if recipe["style"] not in catalog.styles:
        issues.append(Issue("UNKNOWN_STYLE", "style", f"Unknown style {recipe['style']!r}"))
    if recipe["assetManifestVersion"] != catalog.manifest_version:
        issues.append(Issue("MANIFEST_VERSION_MISMATCH", "assetManifestVersion", "Recipe targets another manifest"))

    rig = None
    base = catalog.get(recipe["baseModelId"], "base_model")
    if base is None:
        issues.append(Issue("UNKNOWN_ASSET", "baseModelId", f"Unknown base model {recipe['baseModelId']!r}"))
    elif not base.approved:
        issues.append(Issue("ASSET_NOT_APPROVED", "baseModelId", "Base model licence is not approved"))
    else:
        rig = base.data["rig"]
        if recipe["category"] in catalog.categories and recipe["category"] not in base.data["categories"]:
            issues.append(
                Issue("CATEGORY_NOT_SUPPORTED", "category", f"{base.id} does not support {recipe['category']}")
            )

    used_slots: dict[str, str] = {}
    for i, module_id in enumerate(recipe["modules"]):
        field = f"modules/{i}"
        module = catalog.get(module_id, "module")
        if module is None:
            issues.append(Issue("UNKNOWN_ASSET", field, f"Unknown module {module_id!r}"))
            continue
        if not module.approved:
            issues.append(Issue("ASSET_NOT_APPROVED", field, f"{module_id} licence is not approved"))
            continue
        if rig and rig not in module.data["rigs"]:
            issues.append(Issue("INCOMPATIBLE_MODULE", field, f"{module_id} does not fit rig {rig}"))
        slot = module.data["slot"]
        if slot in used_slots:
            issues.append(Issue("SLOT_CONFLICT", field, f"{module_id} and {used_slots[slot]} share slot {slot}"))
        else:
            used_slots[slot] = module_id

    for i, power_id in enumerate(recipe["powers"]):
        power = catalog.get(power_id, "power_effect")
        if power is None:
            issues.append(Issue("UNKNOWN_ASSET", f"powers/{i}", f"Unknown power {power_id!r}"))
        elif not power.approved:
            issues.append(Issue("ASSET_NOT_APPROVED", f"powers/{i}", f"{power_id} is not approved"))
        elif rig and rig not in power.data["rigs"]:
            issues.append(Issue("UNSUPPORTED_POWER", f"powers/{i}", f"{power_id} is not supported by rig {rig}"))

    for i, trait in enumerate(recipe["personalityTraits"]):
        if trait not in catalog.personality_traits:
            issues.append(Issue("UNKNOWN_TRAIT", f"personalityTraits/{i}", f"Unknown trait {trait!r}"))

    voice = catalog.get(recipe["voiceProfileId"], "voice_profile")
    if voice is None:
        issues.append(Issue("UNKNOWN_ASSET", "voiceProfileId", "Unknown voice profile"))
    elif not voice.approved:
        issues.append(Issue("ASSET_NOT_APPROVED", "voiceProfileId", "Voice profile is not approved"))
    return issues


def validate_recipe(recipe: Any, catalog: Catalog, shared_dir: Path) -> dict[str, Any]:
    issues = recipe_issues(recipe, catalog, shared_dir)
    if issues:
        raise AppError("RECIPE_INVALID", "Character recipe failed validation", [i.as_dict() for i in issues])
    return recipe


def normalize_hex(color: str) -> str:
    return color.upper()


def normalized_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    out = dict(recipe)
    out["palette"] = {k: normalize_hex(v) for k, v in recipe["palette"].items()}
    return out

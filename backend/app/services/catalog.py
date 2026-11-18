"""Asset catalogue backed by the asset registry + licence tables.

The shared manifest (shared/asset-manifests/asset_manifest_v1.json) is the seed source. At runtime the
registry rows in the database are authoritative: an asset is *usable* only when its registry row says
commercial use is approved AND its licence record is approved for commercial use (plan §2.2, §9.2).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import AssetRegistryEntry, Licence

# manifest key -> registry asset_type
ASSET_SECTIONS: dict[str, str] = {
    "baseModels": "base_model",
    "modules": "module",
    "powers": "power_effect",
    "voiceProfiles": "voice_profile",
    "animationClips": "animation_clip",
    "environments": "environment",
    "cameraPresets": "camera_preset",
    "lightingPresets": "lighting_preset",
    "soundEffects": "sound_effect",
    "musicCues": "music_cue",
    "storyTemplates": "story_template",
    "characterTemplates": "character_template",
}
API_TYPE_ALIASES = {
    "character-template": "character_template",
    "base-model": "base_model",
    "module": "module",
    "power": "power_effect",
    "voice": "voice_profile",
    "animation-clip": "animation_clip",
    "environment": "environment",
    "camera-preset": "camera_preset",
    "lighting-preset": "lighting_preset",
    "sound-effect": "sound_effect",
    "music-cue": "music_cue",
    "story-template": "story_template",
}
FORMAT_BY_TYPE = {
    "base_model": "glb",
    "module": "glb",
    "animation_clip": "glb-anim",
    "environment": "glb",
    "voice_profile": "voice-config",
    "sound_effect": "synth-config",
    "music_cue": "synth-config",
}
DEFAULT_LICENCE = "lic_cv_original_v1"


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: Any) -> str:
    raw = data if isinstance(data, bytes) else canonical_json(data).encode()
    return hashlib.sha256(raw).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@dataclass
class CatalogAsset:
    id: str
    asset_type: str
    data: dict[str, Any]
    licence_id: str
    approved: bool


@dataclass
class Catalog:
    manifest: dict[str, Any]
    parts: dict[str, Any]
    assets: dict[str, CatalogAsset] = field(default_factory=dict)

    # ---- construction -------------------------------------------------
    @classmethod
    def from_manifest_files(cls, shared_dir: Path) -> Catalog:
        manifest = load_json(shared_dir / "asset-manifests" / "asset_manifest_v1.json")
        parts = load_json(shared_dir / "asset-manifests" / "procedural_parts_v1.json")
        cat = cls(manifest=manifest, parts=parts)
        licences = {lic["id"]: lic for lic in manifest["licences"]}
        for section, asset_type in ASSET_SECTIONS.items():
            for item in manifest.get(section, []):
                lic = licences[item.get("licenceId", DEFAULT_LICENCE)]
                approved = lic["reviewStatus"] == "approved" and lic["commercialUse"]
                cat.assets[item["id"]] = CatalogAsset(item["id"], asset_type, item, lic["id"], approved)
        return cat

    def refresh_from_db(self, session: Session) -> None:
        """Re-derive approval from the registry + licence tables (authoritative at runtime)."""
        licences = {lic.id: lic for lic in session.scalars(select(Licence))}
        rows = {r.id: r for r in session.scalars(select(AssetRegistryEntry))}
        for asset_id, asset in self.assets.items():
            row = rows.get(asset_id)
            if row is None:
                asset.approved = False
                continue
            lic = licences.get(row.licence_id)
            asset.approved = bool(
                row.commercial_use_approved and lic and lic.commercial_use and lic.review_status == "approved"
            )

    # ---- seeding ------------------------------------------------------
    def seed_registry(self, session: Session) -> None:
        for lic in self.manifest["licences"]:
            if session.get(Licence, lic["id"]) is None:
                session.add(
                    Licence(
                        id=lic["id"],
                        name=lic["name"],
                        licence_url=lic["licenceUrl"],
                        commercial_use=lic["commercialUse"],
                        attribution_required=lic["attributionRequired"],
                        redistribution=lic.get("redistribution", False),
                        derivatives=lic.get("derivatives", False),
                        review_status=lic["reviewStatus"],
                        reviewed_at=lic.get("reviewedAt"),
                        reviewer=lic.get("reviewer"),
                    )
                )
        session.flush()
        version = self.manifest["manifestVersion"]
        for asset in self.assets.values():
            if session.get(AssetRegistryEntry, asset.id) is not None:
                continue  # registry rows are immutable once published; new versions get new IDs
            definition = {"definition": asset.data, "parts": self._parts_for(asset)}
            session.add(
                AssetRegistryEntry(
                    id=asset.id,
                    asset_type=asset.asset_type,
                    asset_version=version,
                    name=asset.data.get("name", asset.id),
                    storage_key=f"catalog/{asset.asset_type}/{asset.id}@{version}",
                    format=FORMAT_BY_TYPE.get(asset.asset_type, "json"),
                    licence_id=asset.licence_id,
                    commercial_use_approved=asset.approved,
                    provenance="Created in-house by the CharacterVerse team (procedural primitives)",
                    sha256=sha256_hex(definition),
                    metadata_json=asset.data,
                )
            )
        session.commit()

    def _parts_for(self, asset: CatalogAsset) -> Any:
        if asset.asset_type == "base_model":
            return self.parts["baseModels"].get(asset.id)
        if asset.asset_type == "module":
            return self.parts["modules"].get(asset.id)
        return None

    # ---- lookups ------------------------------------------------------
    @property
    def manifest_version(self) -> str:
        return self.manifest["manifestVersion"]

    def get(self, asset_id: str, asset_type: str | None = None) -> CatalogAsset | None:
        asset = self.assets.get(asset_id)
        if asset is None or (asset_type and asset.asset_type != asset_type):
            return None
        return asset

    def approved(self, asset_id: str, asset_type: str) -> bool:
        asset = self.get(asset_id, asset_type)
        return bool(asset and asset.approved)

    def of_type(self, asset_type: str, include_unapproved: bool = False) -> list[CatalogAsset]:
        return [a for a in self.assets.values() if a.asset_type == asset_type and (include_unapproved or a.approved)]

    def rig_of(self, base_model_id: str) -> str | None:
        asset = self.get(base_model_id, "base_model")
        return asset.data["rig"] if asset else None

    @property
    def categories(self) -> list[str]:
        return self.manifest["categories"]

    @property
    def styles(self) -> list[str]:
        return self.manifest["styles"]

    @property
    def personality_traits(self) -> list[str]:
        return self.manifest["personalityTraits"]

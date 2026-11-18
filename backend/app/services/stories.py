"""Story + storyboard validation (plan §7.3). Generation is delegated to the TextGenerationProvider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.errors import AppError
from app.services.catalog import Catalog
from app.services.recipes import Issue, _schema_validator

ASSET_FIELDS = (
    ("environmentId", "environment"),
    ("cameraPresetId", "camera_preset"),
    ("lightingPresetId", "lighting_preset"),
)


def storyboard_issues(doc: Any, catalog: Catalog, shared_dir: Path, character_rigs: dict[str, str]) -> list[Issue]:
    validator = _schema_validator(str(shared_dir / "json-schemas" / "storyboard.v1.schema.json"))
    issues = [
        Issue("SCHEMA_VIOLATION", "/".join(str(p) for p in e.path) or "$", e.message)
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    ]
    if issues:
        return issues

    def check_asset(asset_id: str, asset_type: str, field: str) -> bool:
        asset = catalog.get(asset_id, asset_type)
        if asset is None:
            issues.append(Issue("UNKNOWN_ASSET", field, f"Unknown {asset_type} {asset_id!r}"))
            return False
        if not asset.approved:
            issues.append(Issue("ASSET_NOT_APPROVED", field, f"{asset_id} is not approved"))
            return False
        return True

    cast = {c["characterId"] for c in doc["characters"]}
    for cid in cast:
        if cid not in character_rigs:
            issues.append(Issue("UNKNOWN_CHARACTER", "characters", f"Character {cid} is not available to you"))
    if doc["musicCueId"]:
        check_asset(doc["musicCueId"], "music_cue", "musicCueId")
    total = 0
    for i, scene in enumerate(doc["scenes"]):
        base = f"scenes/{i}"
        if scene["sequence"] != i + 1:
            issues.append(Issue("SEQUENCE_GAP", f"{base}/sequence", "Scenes must be numbered 1..n in order"))
        total += scene["durationMs"]
        for field, asset_type in ASSET_FIELDS:
            check_asset(scene[field], asset_type, f"{base}/{field}")
        for j, sfx in enumerate(scene["soundEffectIds"]):
            check_asset(sfx, "sound_effect", f"{base}/soundEffectIds/{j}")
        for j, sc in enumerate(scene["characters"]):
            field = f"{base}/characters/{j}"
            if sc["characterId"] not in cast:
                issues.append(Issue("UNKNOWN_CHARACTER", field, "Character is not in the cast"))
                continue
            if check_asset(sc["actionId"], "animation_clip", f"{field}/actionId"):
                rig = character_rigs.get(sc["characterId"])
                clip = catalog.get(sc["actionId"], "animation_clip")
                if rig and rig not in clip.data["rigs"]:
                    issues.append(
                        Issue(
                            "UNSUPPORTED_ACTION",
                            f"{field}/actionId",
                            f"{sc['actionId']} is not available for rig {rig}",
                        )
                    )
        for j, d in enumerate(scene["dialogue"]):
            if d["characterId"] not in cast:
                issues.append(Issue("UNKNOWN_CHARACTER", f"{base}/dialogue/{j}", "Speaker is not in the cast"))
            if d["startMs"] >= scene["durationMs"]:
                issues.append(
                    Issue(
                        "DIALOGUE_OUT_OF_RANGE", f"{base}/dialogue/{j}/startMs", "Dialogue starts after the scene ends"
                    )
                )
    if total > doc["durationSeconds"] * 1000 + 500:
        issues.append(
            Issue("DURATION_EXCEEDED", "scenes", f"Scenes total {total}ms > {doc['durationSeconds']}s preset")
        )
    return issues


def validate_storyboard(doc: Any, catalog: Catalog, shared_dir: Path, character_rigs: dict[str, str]) -> None:
    issues = storyboard_issues(doc, catalog, shared_dir, character_rigs)
    if issues:
        raise AppError("STORYBOARD_INVALID", "Storyboard failed validation", [i.as_dict() for i in issues])


def storyboard_text(doc: dict[str, Any]) -> str:
    parts = [doc.get("title", ""), doc.get("logline", ""), doc.get("synopsis", "")]
    for scene in doc.get("scenes", []):
        parts.append(scene.get("title", ""))
        parts.append(scene.get("description", ""))
        parts.extend(d.get("line", "") for d in scene.get("dialogue", []))
    return "\n".join(parts)

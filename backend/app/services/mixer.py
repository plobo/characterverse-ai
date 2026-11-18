"""Deterministic fusion resolver (plan §6.3).

This is a controlled trait mixer, not mesh merging. The same algorithm runs on iOS and Android for offline
previews and is pinned by shared/fixtures/mix_golden.json. Rules (documented in docs/ARCHITECTURE.md#fusion):

* Weights are normalised to sum to 1. Sources are ranked by weight desc, ties broken by input order.
* The dominant (rank 0) source always supplies baseModelId, category and style. Skeletons are never blended.
* appearance: proportions and palette are weighted blends; modules are pooled in rank order and filtered
  by target rig, licence approval, one-per-slot and the 6-module limit.
* powers: pooled in rank order, filtered by rig support, max 3.
* personality: pooled in rank order, de-duplicated, max 5.
* voice: the strongest *secondary* contributor (rank 1) supplies the voice; otherwise the dominant's voice.
* A dimension that is not mixed is copied from the dominant source.
* Rounding is floor(x + 0.5) so every platform produces identical values.
"""

from __future__ import annotations

import math
from typing import Any

from app.core.errors import AppError
from app.services.catalog import Catalog

DIMENSIONS = ("appearance", "powers", "personality", "voice")
MAX_MODULES = 6
MAX_POWERS = 3
MAX_TRAITS = 5


def _round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def _round2(x: float) -> float:
    return math.floor(x * 100 + 0.5) / 100


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _plain_sum(values) -> float:
    """Left-to-right IEEE-754 addition. Python 3.12+ sum() uses compensated summation, which would diverge
    from Swift/Kotlin by an ulp and break cross-platform golden parity."""
    total = 0.0
    for v in values:
        total += v
    return total


def _blend_hex(colors: list[str], weights: list[float]) -> str:
    channels = []
    for ch in range(3):
        total = 0.0
        for color, w in zip(colors, weights, strict=True):
            total += w * int(color.lstrip("#")[ch * 2 : ch * 2 + 2], 16)
        channels.append(int(_clamp(_round_half_up(total), 0, 255)))
    return "#{:02X}{:02X}{:02X}".format(*channels)


def default_name(names_by_rank: list[str], source_names: list[str]) -> str:
    first = names_by_rank[0].split()[0]
    second = names_by_rank[1].split()[-1] if len(names_by_rank) > 1 else "Fusion"
    name = f"{first} {second}" if first != second else f"{first} Fusion"
    if name in source_names:
        name = f"{name} Fusion"
    return name[:40].strip()


def resolve_mix(
    sources: list[dict[str, Any]],
    weights: dict[str, float] | None,
    dimensions: list[str],
    catalog: Catalog,
    name: str | None = None,
) -> dict[str, Any]:
    """sources: [{"id": str, "recipe": {...}}]. Returns {recipe, lineage, omitted, warnings, dominantSourceId}."""
    if not 2 <= len(sources) <= 3:
        raise AppError("MIX_INVALID", "Select two or three characters to mix")
    dims = list(DIMENSIONS) if "all" in dimensions else [d for d in DIMENSIONS if d in dimensions]
    if not dims:
        raise AppError("MIX_INVALID", "Choose at least one mix dimension")
    ids = [s["id"] for s in sources]
    if len(set(ids)) != len(ids):
        raise AppError("MIX_INVALID", "Each source character can only be used once")

    raw_w = [float((weights or {}).get(sid, 1.0)) for sid in ids]
    if any(w < 0 for w in raw_w) or _plain_sum(raw_w) <= 0:
        raise AppError("MIX_INVALID", "Weights must be non-negative and not all zero")
    total = _plain_sum(raw_w)
    w = [x / total for x in raw_w]
    order = sorted(range(len(sources)), key=lambda i: (-w[i], i))
    recipes = [s["recipe"] for s in sources]
    dom = recipes[order[0]]

    base_id = dom["baseModelId"]
    rig = catalog.rig_of(base_id)
    omitted: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    rigs = {catalog.rig_of(r["baseModelId"]) for r in recipes}
    if len(rigs) > 1:
        warnings.append(
            {
                "code": "RIG_MISMATCH",
                "message": f"Different body rigs; using {base_id} ({rig}) and keeping compatible parts",
            }
        )

    if "appearance" in dims:
        proportions = {
            key: _clamp(
                _round2(_plain_sum(w[i] * recipes[i]["proportions"][key] for i in range(len(recipes)))), 0.7, 1.3
            )
            for key in ("height", "shoulderWidth", "headScale")
        }
        palette = {
            key: _blend_hex([r["palette"][key] for r in recipes], w) for key in ("primary", "secondary", "accent")
        }
        module_pool = [m for i in order for m in recipes[i]["modules"]]
    else:
        proportions = dict(dom["proportions"])
        palette = {k: v.upper() for k, v in dom["palette"].items()}
        module_pool = list(dom["modules"])

    modules: list[str] = []
    slots: set[str] = set()
    for module_id in module_pool:
        if module_id in modules or any(o["id"] == module_id for o in omitted):
            continue
        module = catalog.get(module_id, "module")
        reason = None
        if module is None or not module.approved:
            reason = "not_approved"
        elif rig not in module.data["rigs"]:
            reason = "incompatible_rig"
        elif module.data["slot"] in slots:
            reason = "slot_taken"
        elif len(modules) >= MAX_MODULES:
            reason = "limit_reached"
        if reason:
            omitted.append({"id": module_id, "kind": "module", "reason": reason})
            continue
        modules.append(module_id)
        slots.add(module.data["slot"])

    power_pool = [p for i in order for p in recipes[i]["powers"]] if "powers" in dims else list(dom["powers"])
    powers: list[str] = []
    for power_id in power_pool:
        if power_id in powers or any(o["id"] == power_id for o in omitted):
            continue
        power = catalog.get(power_id, "power_effect")
        reason = None
        if power is None or not power.approved:
            reason = "not_approved"
        elif rig not in power.data["rigs"]:
            reason = "unsupported_by_rig"
        elif len(powers) >= MAX_POWERS:
            reason = "limit_reached"
        if reason:
            omitted.append({"id": power_id, "kind": "power", "reason": reason})
            continue
        powers.append(power_id)

    trait_pool = (
        [t for i in order for t in recipes[i]["personalityTraits"]]
        if "personality" in dims
        else list(dom["personalityTraits"])
    )
    traits: list[str] = []
    for trait in trait_pool:
        if trait in traits or any(o["id"] == trait for o in omitted):
            continue
        if len(traits) >= MAX_TRAITS:
            omitted.append({"id": trait, "kind": "trait", "reason": "limit_reached"})
            continue
        traits.append(trait)

    voice = recipes[order[1]]["voiceProfileId"] if "voice" in dims else dom["voiceProfileId"]
    if omitted:
        warnings.append({"code": "TRAITS_OMITTED", "message": f"{len(omitted)} trait(s) could not be combined"})

    names_by_rank = [recipes[i]["name"] for i in order]
    recipe = {
        "schemaVersion": 1,
        "name": (name or default_name(names_by_rank, [r["name"] for r in recipes]))[:40],
        "category": dom["category"],
        "baseModelId": base_id,
        "style": dom["style"],
        "proportions": proportions,
        "palette": palette,
        "modules": modules,
        "powers": powers,
        "personalityTraits": traits,
        "voiceProfileId": voice,
        "assetManifestVersion": catalog.manifest_version,
    }
    lineage = [{"sourceCharacterId": ids[i], "weight": round(w[i], 4), "dimensions": dims} for i in range(len(ids))]
    return {
        "recipe": recipe,
        "lineage": lineage,
        "omitted": omitted,
        "warnings": warnings,
        "dominantSourceId": ids[order[0]],
    }

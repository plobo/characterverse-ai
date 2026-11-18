"""Preview assembly with recipe-hash caching (plan §7.5): identical recipes reuse the same GLB + thumbnail."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domain.models import MediaAsset
from app.services.assembly import assemble_parts, build_glb
from app.services.catalog import canonical_json, sha256_hex
from app.services.drawing import render_thumbnail


def recipe_hash(recipe: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(recipe).encode())


def ensure_preview(container: Any, session: Session, recipe: dict[str, Any], owner_id: Any = None) -> dict[str, Any]:
    """User previews live under users/{id}/ (removed on account deletion); catalogue previews are shared."""
    h = recipe_hash(recipe)
    prefix = f"users/{owner_id}/previews" if owner_id else "catalog/previews"
    glb_key, png_key = f"{prefix}/{h}.glb", f"{prefix}/{h}.png"
    storage = container.storage
    cached = storage.exists(glb_key) and storage.exists(png_key)
    if not cached:
        parts = assemble_parts(recipe, container.catalog)
        glb = build_glb(parts, recipe.get("name", "character"))
        png = render_thumbnail(parts)
        storage.put(glb_key, glb)
        storage.put(png_key, png)
        for key, data, mime in ((glb_key, glb, "model/gltf-binary"), (png_key, png, "image/png")):
            if session.query(MediaAsset).filter_by(storage_key=key).one_or_none() is None:
                session.add(
                    MediaAsset(
                        owner_user_id=owner_id,
                        asset_type="character_preview",
                        storage_key=key,
                        mime_type=mime,
                        file_size=len(data),
                        sha256=sha256_hex(data),
                    )
                )
        session.commit()
    ttl = container.settings.signed_url_ttl_seconds
    glb_url, exp = storage.signed_url(glb_key, ttl)
    png_url, _ = storage.signed_url(png_key, ttl)
    return {"recipeHash": h, "cached": cached, "glbUrl": glb_url, "thumbnailUrl": png_url, "expiresAt": exp}

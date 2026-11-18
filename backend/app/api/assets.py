from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_container, get_session
from app.core.container import Container
from app.core.errors import AppError
from app.domain.models import AssetRegistryEntry, Licence
from app.schemas.api import AssetDetailOut, AssetList, AssetOut, CatalogManifestOut, LicenceOut, SignedUrl
from app.services.catalog import API_TYPE_ALIASES, ASSET_SECTIONS
from app.services.previews import ensure_preview

router = APIRouter(prefix="/v1", tags=["assets"])


def asset_out(row: AssetRegistryEntry, approved: bool) -> AssetOut:
    return AssetOut(
        id=row.id,
        type=row.asset_type,
        name=row.name,
        version=row.asset_version,
        licence_id=row.licence_id,
        commercial_use_approved=approved,
        sha256=row.sha256,
        metadata=row.metadata_json,
    )


@router.get("/catalog/manifest", response_model=CatalogManifestOut)
def catalog_manifest(container: Container = Depends(get_container)) -> CatalogManifestOut:
    """Public catalogue snapshot (approved assets only) used by mobile clients to refresh their bundled copy."""
    cat = container.catalog
    manifest = {k: v for k, v in cat.manifest.items() if k not in ASSET_SECTIONS}
    for section in ASSET_SECTIONS:
        manifest[section] = [a for a in cat.manifest.get(section, []) if cat.assets[a["id"]].approved]
    return CatalogManifestOut(manifest_version=cat.manifest_version, manifest=manifest, parts=cat.parts)


@router.get("/assets", response_model=AssetList)
def list_assets(
    type: str | None = Query(default=None, description="e.g. character-template, environment"),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> AssetList:
    """Public catalogue. Only licence-approved assets are listed."""
    q = session.query(AssetRegistryEntry)
    if type:
        asset_type = API_TYPE_ALIASES.get(type, type)
        q = q.filter(AssetRegistryEntry.asset_type == asset_type)
    rows = q.order_by(AssetRegistryEntry.asset_type, AssetRegistryEntry.id).all()
    return AssetList(items=[asset_out(r, True) for r in rows if container.catalog.approved(r.id, r.asset_type)])


def _approved_row(asset_id: str, container: Container, session: Session) -> AssetRegistryEntry:
    row = session.get(AssetRegistryEntry, asset_id)
    if row is None or not container.catalog.approved(row.id, row.asset_type):
        raise AppError("NOT_FOUND", "Asset not found")
    return row


@router.get("/assets/{asset_id}", response_model=AssetDetailOut)
def get_asset(
    asset_id: str, container: Container = Depends(get_container), session: Session = Depends(get_session)
) -> AssetDetailOut:
    row = _approved_row(asset_id, container, session)
    lic = session.get(Licence, row.licence_id)
    base = asset_out(row, True).model_dump()
    return AssetDetailOut(
        **base,
        licence=LicenceOut(
            id=lic.id,
            name=lic.name,
            licence_url=lic.licence_url,
            commercial_use=lic.commercial_use,
            attribution_required=lic.attribution_required,
            review_status=lic.review_status,
            reviewed_at=lic.reviewed_at,
            reviewer=lic.reviewer,
        ),
    )


@router.get("/assets/{asset_id}/preview-url", response_model=SignedUrl)
def asset_preview_url(
    asset_id: str, container: Container = Depends(get_container), session: Session = Depends(get_session)
) -> SignedUrl:
    """Signed URL to a GLB preview. Character templates and base models are assembled procedurally."""
    row = _approved_row(asset_id, container, session)
    cat = container.catalog
    if row.asset_type == "character_template":
        recipe = cat.get(asset_id).data["recipe"]
    elif row.asset_type == "base_model":
        template = next(t for t in cat.manifest["characterTemplates"])["recipe"]
        recipe = {
            **template,
            "baseModelId": asset_id,
            "modules": [],
            "category": cat.get(asset_id).data["categories"][0],
        }
    else:
        raise AppError("NOT_FOUND", "This asset type has no 3D preview")
    preview = ensure_preview(container, session, recipe)
    return SignedUrl(url=preview["glbUrl"], expires_at=preview["expiresAt"])

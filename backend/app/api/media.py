from __future__ import annotations

import mimetypes
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import audit, current_user, feedback_for, get_container, get_session, moderate
from app.core.container import Container
from app.core.db import utcnow
from app.core.errors import AppError
from app.domain.models import MediaAsset, Report, User
from app.schemas.api import (
    ModerationCheckRequest,
    ModerationFeedback,
    PresignOut,
    PresignRequest,
    ReportOut,
    ReportRequest,
)
from app.services.catalog import sha256_hex
from app.services.moderation import Moderator

router = APIRouter(prefix="/v1", tags=["media", "moderation"])

MAGIC = {
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "audio/wav": [b"RIFF"],
    "audio/mpeg": [b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"],
}
EXT = {"image/png": "png", "image/jpeg": "jpg", "audio/wav": "wav", "audio/mpeg": "mp3"}


@router.post("/uploads/presign", response_model=PresignOut)
def presign_upload(
    body: PresignRequest,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
):
    """Issue a short-lived signed PUT URL. Users must confirm they hold the rights to what they upload."""
    if not body.rights_confirmed:
        raise AppError("UPLOAD_REJECTED", "Confirm you own or have rights to this file")
    if body.file_size > container.settings.max_upload_bytes:
        raise AppError("UPLOAD_REJECTED", "File is too large")
    moderate(container, session, user, body.file_name, "other")
    asset_id = uuid.uuid4()
    key = f"uploads/{user.id}/{asset_id}.{EXT[body.mime_type]}"
    session.add(
        MediaAsset(
            id=asset_id,
            owner_user_id=user.id,
            asset_type=body.purpose,
            storage_key=key,
            mime_type=body.mime_type,
            file_size=body.file_size,
            status="pending_upload",
            expires_at=utcnow() + timedelta(days=30),
        )
    )
    audit(session, user, "upload.presigned", "media_asset", asset_id, mime=body.mime_type)
    session.commit()
    url, exp = container.storage.signed_url(key, container.settings.signed_url_ttl_seconds, method="PUT")
    return PresignOut(
        asset_id=str(asset_id), upload_url=url, method="PUT", headers={"Content-Type": body.mime_type}, expires_at=exp
    )


@router.put("/upload/{key:path}", status_code=204, include_in_schema=True)
async def put_upload(
    key: str,
    request: Request,
    exp: int = Query(),
    sig: str = Query(),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
):
    container.storage.verify(key, exp, sig, method="PUT")
    asset = session.query(MediaAsset).filter_by(storage_key=key).one_or_none()
    if asset is None or asset.status != "pending_upload":
        raise AppError("UPLOAD_REJECTED", "Upload slot is not available")
    limit = min(asset.file_size, container.settings.max_upload_bytes)
    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():  # stop reading as soon as the declared size is exceeded
        received += len(chunk)
        if received > limit:
            raise AppError("UPLOAD_REJECTED", "File is larger than declared")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not any(data.startswith(m) for m in MAGIC[asset.mime_type]):
        raise AppError("UPLOAD_REJECTED", "File content does not match its declared type")
    container.storage.put(key, data)
    asset.file_size, asset.sha256, asset.status = len(data), sha256_hex(data), "ready"
    session.commit()
    return Response(status_code=204)


@router.get("/media/{key:path}", include_in_schema=True)
def get_media(key: str, exp: int = Query(), sig: str = Query(), container: Container = Depends(get_container)):
    """Serve a stored object for a valid, unexpired signed URL (no credentials ever reach clients)."""
    container.storage.verify(key, exp, sig, method="GET")
    path = container.storage.path_for(key)
    if not path.exists():
        raise AppError("NOT_FOUND", "Media not found")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if path.suffix == ".glb":
        media_type = "model/gltf-binary"
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, max-age=300"})


@router.post("/moderation/check", response_model=ModerationFeedback)
def moderation_check(
    body: ModerationCheckRequest,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
):
    """Pre-flight originality check for editors (never raises; returns the decision)."""
    moderator: Moderator = container.moderator
    try:
        result = moderate(container, session, user, body.text, body.content_type)
    except AppError:
        result = moderator.check(body.text)
    return ModerationFeedback(**feedback_for(result))


@router.post("/reports", response_model=ReportOut, status_code=201)
def create_report(body: ReportRequest, user: User = Depends(current_user), session: Session = Depends(get_session)):
    """Report / takedown request. Reviewed by trust & safety; outcome recorded in the audit log."""
    report = Report(
        reporter_user_id=user.id,
        content_type=body.content_type,
        content_id=body.content_id,
        reason=body.reason,
        details=body.details,
    )
    session.add(report)
    session.flush()
    audit(session, user, "report.created", "report", report.id, reason=body.reason)
    session.commit()
    return ReportOut(id=str(report.id), status=report.status, created_at=report.created_at)

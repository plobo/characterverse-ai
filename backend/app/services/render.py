"""Render job lifecycle (plan §8.3): durable state in the DB, idempotency keys, cancellation, retries."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import AppError
from app.domain.models import Character, Project, RenderJob
from app.services.catalog import sha256_hex
from app.workers.renderer import RESOLUTIONS

ACTIVE = ("queued", "processing")
STAGES = ["queued", "preparing", "rendering_scenes", "composing", "uploading", "completed"]


def create_render_job(
    session: Session,
    container: Any,
    user_id: uuid.UUID,
    project: Project,
    storyboard: dict,
    idempotency_key: str,
    quality: str,
    aspect_ratio: str | None,
) -> tuple[RenderJob, bool]:
    if not idempotency_key or len(idempotency_key) > 128:
        raise AppError("VALIDATION_FAILED", "Idempotency-Key header (1-128 chars) is required")
    aspect = aspect_ratio or storyboard["aspectRatio"]
    request_hash = sha256_hex(
        {
            "project": str(project.id),
            "version": project.version,
            "quality": quality,
            "aspect": aspect,
            "storyboard": storyboard,
        }
    )
    existing = session.scalar(
        select(RenderJob).where(RenderJob.owner_user_id == user_id, RenderJob.idempotency_key == idempotency_key)
    )
    if existing:
        if existing.request_hash != request_hash:
            raise AppError("IDEMPOTENCY_CONFLICT", "Idempotency-Key was already used for a different request")
        return existing, False

    active = session.scalar(
        select(func.count())
        .select_from(RenderJob)
        .where(RenderJob.owner_user_id == user_id, RenderJob.status.in_(ACTIVE))
    )
    if active >= container.settings.max_active_renders_per_user:
        raise AppError("QUOTA_EXCEEDED", "Too many renders in progress; wait for one to finish or cancel it")

    cast_ids = [c["characterId"] for c in storyboard["characters"]]
    chars = {
        str(c.id): c
        for c in session.scalars(
            select(Character).where(
                Character.id.in_([uuid.UUID(cid) for cid in cast_ids]),
                Character.owner_user_id == user_id,
                Character.deleted_at.is_(None),
            )
        )
    }
    width, height = RESOLUTIONS[(quality, aspect)]
    settings = {
        "quality": quality,
        "aspectRatio": aspect,
        "width": width,
        "height": height,
        "fps": container.settings.render_fps,
        "projectVersion": project.version,
        "storyboard": storyboard,
        "characters": {cid: {"name": c.name, "recipe": c.recipe_json} for cid, c in chars.items()},
    }
    job = RenderJob(
        project_id=project.id,
        owner_user_id=user_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        settings_json=settings,
        logs_json=[],
    )
    session.add(job)
    session.commit()
    return job, True


def cancel_job(session: Session, job: RenderJob) -> RenderJob:
    if job.status == "queued":
        job.status = "cancelled"
        job.progress_stage = "cancelled"
        job.completed_at = utcnow()
    elif job.status == "processing":
        job.cancel_requested = True
    else:
        raise AppError("RENDER_NOT_CANCELLABLE", f"A {job.status} job cannot be cancelled")
    session.commit()
    return job


def retry_job(session: Session, job: RenderJob) -> RenderJob:
    if job.status not in ("failed", "cancelled"):
        raise AppError("RENDER_NOT_RETRYABLE", f"A {job.status} job cannot be retried")
    job.status = "queued"
    job.progress_stage = "queued"
    job.progress_percent = 0
    job.error_code = None
    job.error_message = None
    job.attempts = 0
    job.cancel_requested = False
    job.lease_expires_at = None
    job.next_attempt_at = None
    job.completed_at = None
    session.commit()
    return job


def backoff_seconds(attempt: int, base: float, cap: float) -> float:
    return min(cap, base * (2 ** max(0, attempt - 1)))


def lease_until(seconds: int):
    return utcnow() + timedelta(seconds=seconds)

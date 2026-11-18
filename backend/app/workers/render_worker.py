"""Idempotent render worker. Safe under at-least-once delivery and worker restarts (plan §8.3)."""

from __future__ import annotations

import shutil
import time
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import imageio_ffmpeg
from sqlalchemy import or_, update
from sqlalchemy.orm.exc import ObjectDeletedError, StaleDataError

from app.core.db import utcnow
from app.domain.models import MediaAsset, RenderJob, User
from app.services.assembly import assemble_parts
from app.services.catalog import sha256_hex
from app.services.recipes import recipe_issues
from app.services.render import backoff_seconds
from app.services.stories import storyboard_issues
from app.workers.renderer import (
    PermanentRenderError,
    ProceduralRenderer,
    RenderCancelled,
    RenderPlan,
    TransientRenderError,
)


def _log(job: RenderJob, message: str) -> None:
    job.logs_json = [*(job.logs_json or []), {"at": utcnow().isoformat(), "message": message[:500]}][-50:]


def claim(container: Any, job_id: uuid.UUID) -> bool:
    """Atomically move a job to processing. Returns False if another worker owns it or it is finished."""
    now = utcnow()
    with container.db.session() as s:
        res = s.execute(
            update(RenderJob)
            .where(
                RenderJob.id == job_id,
                RenderJob.cancel_requested.is_(False),
                or_(
                    RenderJob.status == "queued",
                    (RenderJob.status == "processing") & (RenderJob.lease_expires_at < now),
                ),
            )
            .where(or_(RenderJob.next_attempt_at.is_(None), RenderJob.next_attempt_at <= now))
            .values(
                status="processing",
                progress_stage="preparing",
                progress_percent=5,
                attempts=RenderJob.attempts + 1,
                lease_expires_at=now + timedelta(seconds=container.settings.render_lease_seconds),
                started_at=now,
            )
        )
        s.commit()
        return res.rowcount == 1


def build_plan(container: Any, settings: dict[str, Any]) -> RenderPlan:
    catalog = container.catalog
    storyboard = settings["storyboard"]
    rigs, parts, names, voices, powers = {}, {}, {}, {}, {}
    for cid, info in settings["characters"].items():
        recipe = info["recipe"]
        if recipe_issues(recipe, catalog, container.settings.shared_dir):  # licence may have been revoked since submit
            raise PermanentRenderError("RECIPE_INVALID", f"{info['name']} uses assets that are no longer licensed")
        rigs[cid] = catalog.rig_of(recipe["baseModelId"]) or "humanoid_v1"
        parts[cid] = assemble_parts(recipe, catalog)
        names[cid] = info["name"]
        voice = catalog.get(recipe["voiceProfileId"], "voice_profile")
        voices[cid] = voice.data if voice else {"baseHz": 200}
        powers[cid] = recipe["powers"]
    issues = storyboard_issues(storyboard, catalog, container.settings.shared_dir, rigs)
    if issues:
        raise PermanentRenderError("STORYBOARD_INVALID", "; ".join(f"{i.field}: {i.code}" for i in issues[:5]))
    data = {a.id: a.data for a in catalog.assets.values()}
    return RenderPlan(
        width=settings["width"],
        height=settings["height"],
        fps=settings["fps"],
        storyboard=storyboard,
        character_parts=parts,
        character_names=names,
        character_voices=voices,
        character_powers=powers,
        catalog_data=data,
    )


def make_renderer(container: Any):
    factory = container.extras.get("renderer_factory")
    if factory:
        return factory()
    return ProceduralRenderer(imageio_ffmpeg.get_ffmpeg_exe())


def process_render_job(container: Any, job_id: uuid.UUID) -> str:
    """Run one delivery of a job. Returns the resulting status (for tests/logging)."""
    if not claim(container, job_id):
        with container.db.session() as s:
            job = s.get(RenderJob, job_id)
            dead = job and job.status == "processing" and job.lease_expires_at and job.lease_expires_at < utcnow()
            if job and job.cancel_requested and (job.status == "queued" or dead):
                job.status, job.progress_stage, job.completed_at = "cancelled", "cancelled", utcnow()
                s.commit()
            return job.status if job else "missing"

    started = time.monotonic()
    work = Path(container.settings.work_dir) / str(job_id)
    with container.db.session() as s:
        job = s.get(RenderJob, job_id)
        assert job is not None

        def progress(stage: str, pct: int) -> None:
            job.progress_stage, job.progress_percent = stage, pct
            job.lease_expires_at = utcnow() + timedelta(seconds=container.settings.render_lease_seconds)
            try:
                s.commit()
            except (StaleDataError, ObjectDeletedError) as exc:
                s.rollback()
                raise RenderCancelled() from exc

        def cancelled() -> bool:
            with container.db.session() as probe:  # independent read: the job or its owner may have been deleted
                row = probe.get(RenderJob, job_id)
                owner = probe.get(User, job.owner_user_id)
                return row is None or bool(row.cancel_requested) or owner is None or owner.deleted_at is not None

        try:
            plan = build_plan(container, job.settings_json)
            renderer = make_renderer(container)
            mp4, thumb, duration_ms = renderer.render(plan, work, cancelled, progress)
            if cancelled():
                raise RenderCancelled()
            progress("uploading", 92)
            video_key = f"renders/{job.owner_user_id}/{job.id}/video.mp4"
            thumb_key = f"renders/{job.owner_user_id}/{job.id}/thumbnail.png"
            container.storage.put_file(video_key, mp4)
            container.storage.put_file(thumb_key, thumb)
            video = _upsert_media(s, job, video_key, "video/mp4", "rendered_video", mp4, duration_ms)
            image = _upsert_media(s, job, thumb_key, "image/png", "render_thumbnail", thumb, None)
            job.output_asset_id, job.thumbnail_asset_id = video.id, image.id
            job.status, job.progress_stage, job.progress_percent = "completed", "completed", 100
            job.completed_at = utcnow()
            job.lease_expires_at = None
            _log(job, f"completed with {renderer.name} in {time.monotonic() - started:.1f}s")
        except RenderCancelled:
            job.status, job.progress_stage, job.completed_at = "cancelled", "cancelled", utcnow()
            _log(job, "cancelled by user")
        except PermanentRenderError as exc:
            job.status, job.progress_stage, job.error_code, job.error_message = "failed", "failed", exc.code, str(exc)
            job.completed_at = utcnow()
            _log(job, f"permanent failure {exc.code}")
        except (TransientRenderError, OSError) as exc:
            _handle_transient(container, job, exc)
        except Exception as exc:  # noqa: BLE001 - unknown errors are treated as transient but bounded
            _handle_transient(container, job, exc)
        finally:
            shutil.rmtree(work, ignore_errors=True)
            try:
                job.compute_ms = (job.compute_ms or 0) + int((time.monotonic() - started) * 1000)
                s.commit()
                status = job.status
                retry_at = job.next_attempt_at if status == "queued" else None
            except (StaleDataError, ObjectDeletedError):  # account deleted mid-render: nothing left to update
                s.rollback()
                return "deleted"
    if retry_at is not None and container.queue is not None:
        delay = max(0.0, (retry_at - utcnow()).total_seconds())
        container.queue.enqueue(job_id, delay=delay)
    return status


def _handle_transient(container: Any, job: RenderJob, exc: Exception) -> None:
    code = getattr(exc, "code", "RENDER_TRANSIENT")
    _log(job, f"attempt {job.attempts} failed: {type(exc).__name__}: {exc}")
    if job.attempts >= container.settings.render_max_attempts:
        job.status, job.progress_stage = "failed", "failed"
        job.error_code, job.error_message = "RENDER_RETRIES_EXHAUSTED", str(exc)[:500]
        job.completed_at = utcnow()
        return
    delay = backoff_seconds(
        job.attempts, container.settings.render_backoff_base_seconds, container.settings.render_backoff_cap_seconds
    )
    job.status, job.progress_stage, job.progress_percent = "queued", "queued", 0
    job.error_code = code
    job.lease_expires_at = None
    job.next_attempt_at = utcnow() + timedelta(seconds=delay)


def _upsert_media(s, job: RenderJob, key: str, mime: str, kind: str, path: Path, duration_ms: int | None):
    existing = s.query(MediaAsset).filter_by(storage_key=key).one_or_none()
    data = Path(path).read_bytes()
    asset = existing or MediaAsset(owner_user_id=job.owner_user_id, asset_type=kind, storage_key=key, mime_type=mime)
    asset.file_size, asset.duration_ms, asset.sha256, asset.status = len(data), duration_ms, sha256_hex(data), "ready"
    if existing is None:
        s.add(asset)
    s.flush()
    return asset

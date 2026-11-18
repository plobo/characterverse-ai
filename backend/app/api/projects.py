from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    audit,
    current_user,
    feedback_for,
    get_container,
    get_owned,
    get_session,
    moderate,
    rate_limit,
)
from app.core.container import Container
from app.core.db import utcnow
from app.core.errors import AppError
from app.domain.models import Character, MediaAsset, Project, RenderJob, Scene, User
from app.schemas.api import (
    CreateProjectRequest,
    CreateRenderRequest,
    DownloadUrlOut,
    GenerateStoryRequest,
    GenerateStoryResponse,
    ProjectList,
    ProjectOut,
    RenderJobList,
    RenderJobOut,
    ScenePatch,
    StoryboardRequest,
    UpdateProjectRequest,
    dump,
)
from app.services.catalog import sha256_hex
from app.services.render import cancel_job, create_render_job, retry_job
from app.services.stories import storyboard_text, validate_storyboard

router = APIRouter(prefix="/v1", tags=["stories", "projects", "renders"])
HEADER_KEYS = (
    "title",
    "logline",
    "synopsis",
    "durationSeconds",
    "aspectRatio",
    "language",
    "characters",
    "musicCueId",
    "schemaVersion",
)


# ------------------------------------------------------------------ helpers
def owned_character_rigs(session: Session, container: Container, user: User, ids: list[str]) -> dict[str, str]:
    rigs = {}
    for cid in ids:
        try:
            c = session.get(Character, uuid.UUID(cid))
        except ValueError:
            continue
        if c and c.owner_user_id == user.id and c.deleted_at is None:
            rigs[cid] = container.catalog.rig_of(c.recipe_json["baseModelId"]) or "humanoid_v1"
    return rigs


def storyboard_of(session: Session, project: Project) -> dict[str, Any] | None:
    header = project.settings_json.get("storyboard")
    if not header:
        return None
    scenes = session.scalars(select(Scene).where(Scene.project_id == project.id).order_by(Scene.sequence_number))
    return {**header, "scenes": [s.scene_json for s in scenes]}


def project_out(session: Session, p: Project) -> ProjectOut:
    return ProjectOut(
        id=str(p.id),
        title=p.title,
        description=p.description,
        status=p.status,
        version=p.version,
        storyboard=storyboard_of(session, p),
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def store_storyboard(session: Session, container: Container, user: User, project: Project, doc: dict) -> None:
    rigs = owned_character_rigs(session, container, user, [c["characterId"] for c in doc["characters"]])
    validate_storyboard(doc, container.catalog, container.settings.shared_dir, rigs)
    moderate(container, session, user, storyboard_text(doc), "dialogue", str(project.id))
    for old in session.scalars(select(Scene).where(Scene.project_id == project.id)):
        session.delete(old)
    session.flush()
    for scene in doc["scenes"]:
        session.add(
            Scene(
                id=f"{project.id.hex[:12]}_{scene['sceneId']}"[:64],
                project_id=project.id,
                sequence_number=scene["sequence"],
                duration_ms=scene["durationMs"],
                environment_asset_id=scene["environmentId"],
                camera_preset_id=scene["cameraPresetId"],
                scene_json=scene,
            )
        )
    project.settings_json = {**project.settings_json, "storyboard": {k: doc[k] for k in HEADER_KEYS}}
    project.version += 1
    project.updated_at = utcnow()


# ------------------------------------------------------------------ stories
@router.post("/stories/generate", response_model=GenerateStoryResponse)
def generate_story(
    body: GenerateStoryRequest,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> GenerateStoryResponse:
    """Prompt moderation -> structured script/storyboard (LLM) -> schema + registry validation."""
    rate_limit(container, user, "generate")
    mod = moderate(container, session, user, f"{body.title or ''} {body.prompt}", "story_prompt")
    cast = [get_owned(session, Character, cid, user) for cid in body.character_ids]
    cat = container.catalog
    request = dump(body)
    request["characters"] = [
        {
            "characterId": str(c.id),
            "displayName": c.name,
            "rig": cat.rig_of(c.recipe_json["baseModelId"]),
            "traits": c.recipe_json["personalityTraits"],
            "powers": c.recipe_json["powers"],
        }
        for c in cast
    ]
    cache_key = f"users/{user.id}/stories/{sha256_hex({'req': request, 'manifest': cat.manifest_version})}.json"
    cached = container.storage.exists(cache_key)
    if cached:
        import json

        doc = json.loads(container.storage.path_for(cache_key).read_bytes())
    else:
        vocab = {
            "environments": [e.id for e in cat.of_type("environment")],
            "clipRigs": {c.id: c.data["rigs"] for c in cat.of_type("animation_clip")},
        }
        doc = container.text_provider.storyboard(request, vocab)
    rigs = {c["characterId"]: c["rig"] for c in request["characters"]}
    validate_storyboard(doc, cat, container.settings.shared_dir, rigs)
    if not cached:
        import json

        container.storage.put(cache_key, json.dumps(doc).encode())
    info = container.text_provider.info
    return GenerateStoryResponse(
        storyboard=doc,
        moderation=feedback_for(mod),
        cached=cached,
        provider={"name": info.name, "version": info.version, "local": info.local},
    )


# ------------------------------------------------------------------ projects
@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(
    body: CreateProjectRequest,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> ProjectOut:
    moderate(container, session, user, f"{body.title} {body.description}", "other")
    p = Project(owner_user_id=user.id, title=body.title, description=body.description, settings_json={})
    session.add(p)
    session.flush()
    if body.storyboard:
        store_storyboard(session, container, user, p, dump(body.storyboard))
    audit(session, user, "project.created", "project", p.id)
    session.commit()
    return project_out(session, p)


@router.get("/projects", response_model=ProjectList)
def list_projects(user: User = Depends(current_user), session: Session = Depends(get_session)) -> ProjectList:
    rows = session.scalars(
        select(Project)
        .where(Project.owner_user_id == user.id, Project.deleted_at.is_(None))
        .order_by(Project.updated_at.desc())
    )
    return ProjectList(items=[project_out(session, p) for p in rows])


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)):
    return project_out(session, get_owned(session, Project, project_id, user))


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: str,
    body: UpdateProjectRequest,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
):
    p = get_owned(session, Project, project_id, user)
    if body.title is not None:
        moderate(container, session, user, body.title, "other")
        p.title = body.title
    if body.description is not None:
        p.description = body.description
    if body.status is not None:
        p.status = body.status
    p.updated_at = utcnow()
    session.commit()
    return project_out(session, p)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)):
    p = get_owned(session, Project, project_id, user)
    p.deleted_at = utcnow()
    audit(session, user, "project.deleted", "project", p.id)
    session.commit()
    return Response(status_code=204)


@router.post("/projects/{project_id}/storyboard", response_model=ProjectOut)
def save_storyboard(
    project_id: str,
    body: StoryboardRequest,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
):
    """Replace the project's storyboard (validated against schema + registry + cast ownership)."""
    p = get_owned(session, Project, project_id, user)
    store_storyboard(session, container, user, p, dump(body.storyboard))
    session.commit()
    return project_out(session, p)


@router.patch("/projects/{project_id}/scenes/{scene_id}", response_model=ProjectOut)
def patch_scene(
    project_id: str,
    scene_id: str,
    body: ScenePatch,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
):
    p = get_owned(session, Project, project_id, user)
    doc = storyboard_of(session, p)
    if doc is None:
        raise AppError("NOT_FOUND", "Project has no storyboard yet")
    scene = next((s for s in doc["scenes"] if s["sceneId"] == scene_id), None)
    if scene is None:
        raise AppError("NOT_FOUND", "Scene not found")
    patch = body.model_dump(by_alias=True, exclude_unset=True)
    scene.update(patch)
    store_storyboard(session, container, user, p, doc)
    session.commit()
    return project_out(session, p)


# ------------------------------------------------------------------ renders
def job_out(session: Session, j: RenderJob) -> RenderJobOut:
    s = j.settings_json
    duration = None
    if j.output_asset_id:
        media = session.get(MediaAsset, j.output_asset_id)
        duration = media.duration_ms if media else None
    project = session.get(Project, j.project_id)
    return RenderJobOut(
        id=str(j.id),
        project_id=str(j.project_id),
        project_title=project.title if project else None,
        status=j.status,
        progress_stage=j.progress_stage,
        progress_percent=j.progress_percent,
        quality=s["quality"],
        aspect_ratio=s["aspectRatio"],
        width=s["width"],
        height=s["height"],
        error_code=j.error_code,
        attempts=j.attempts,
        cancel_requested=j.cancel_requested,
        duration_ms=duration,
        created_at=j.created_at,
        started_at=j.started_at,
        completed_at=j.completed_at,
    )


@router.post(
    "/projects/{project_id}/renders",
    response_model=RenderJobOut,
    status_code=201,
    responses={200: {"model": RenderJobOut, "description": "Idempotent replay of an existing job"}},
)
def submit_render(
    project_id: str,
    body: CreateRenderRequest,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> RenderJobOut:
    p = get_owned(session, Project, project_id, user)
    doc = storyboard_of(session, p)
    if doc is None:
        raise AppError("STORYBOARD_INVALID", "Create a storyboard before rendering")
    rigs = owned_character_rigs(session, container, user, [c["characterId"] for c in doc["characters"]])
    validate_storyboard(doc, container.catalog, container.settings.shared_dir, rigs)
    job, created = create_render_job(
        session, container, user.id, p, doc, idempotency_key, body.quality, body.aspect_ratio
    )
    if created:
        audit(session, user, "render.submitted", "render_job", job.id, quality=body.quality)
        session.commit()
        container.queue.enqueue(job.id)
        session.refresh(job)
    else:
        response.status_code = 200
    return job_out(session, job)


@router.get("/renders", response_model=RenderJobList)
def list_renders(
    project_id: str | None = Query(default=None, alias="projectId"),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> RenderJobList:
    q = select(RenderJob).where(RenderJob.owner_user_id == user.id)
    if project_id:
        q = q.where(RenderJob.project_id == uuid.UUID(project_id))
    return RenderJobList(items=[job_out(session, j) for j in session.scalars(q.order_by(RenderJob.created_at.desc()))])


@router.get("/renders/{job_id}", response_model=RenderJobOut)
def get_render(job_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)):
    return job_out(session, get_owned(session, RenderJob, job_id, user))


@router.post("/renders/{job_id}/cancel", response_model=RenderJobOut)
def cancel_render(job_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)):
    job = cancel_job(session, get_owned(session, RenderJob, job_id, user))
    audit(session, user, "render.cancelled", "render_job", job.id)
    session.commit()
    return job_out(session, job)


@router.post("/renders/{job_id}/retry", response_model=RenderJobOut)
def retry_render(
    job_id: str,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
):
    rate_limit(container, user, "render-retry")
    job = retry_job(session, get_owned(session, RenderJob, job_id, user))
    container.queue.enqueue(job.id)
    session.refresh(job)
    return job_out(session, job)


@router.get("/renders/{job_id}/download-url", response_model=DownloadUrlOut)
def download_url(
    job_id: str,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> DownloadUrlOut:
    job = get_owned(session, RenderJob, job_id, user)
    if job.status != "completed" or not job.output_asset_id:
        raise AppError("RENDER_NOT_READY", "This render has not finished yet")
    video = session.get(MediaAsset, job.output_asset_id)
    ttl = container.settings.signed_url_ttl_seconds
    url, exp = container.storage.signed_url(video.storage_key, ttl)
    thumb_url = None
    if job.thumbnail_asset_id:
        thumb = session.get(MediaAsset, job.thumbnail_asset_id)
        thumb_url, _ = container.storage.signed_url(thumb.storage_key, ttl)
    return DownloadUrlOut(
        url=url, thumbnail_url=thumb_url, expires_at=exp, mime_type=video.mime_type, file_size=video.file_size
    )

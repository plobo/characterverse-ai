"""Account data export and deletion (plan §9.2, acceptance criterion 14)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.domain.models import (
    AuditEvent,
    Character,
    CharacterLineage,
    CharacterVersion,
    MediaAsset,
    Mix,
    ModerationEvent,
    Project,
    RenderJob,
    Report,
    Scene,
    User,
)


def _row(obj: Any, *fields: str) -> dict[str, Any]:
    out = {}
    for f in fields:
        v = getattr(obj, f)
        out[f] = v.isoformat() if hasattr(v, "isoformat") else (str(v) if hasattr(v, "hex") else v)
    return out


def export_account(session: Session, user: User) -> dict[str, Any]:
    chars = list(session.scalars(select(Character).where(Character.owner_user_id == user.id)))
    projects = list(session.scalars(select(Project).where(Project.owner_user_id == user.id)))
    scenes = list(session.scalars(select(Scene).where(Scene.project_id.in_([p.id for p in projects]))))
    renders = list(session.scalars(select(RenderJob).where(RenderJob.owner_user_id == user.id)))
    media = list(session.scalars(select(MediaAsset).where(MediaAsset.owner_user_id == user.id)))
    return {
        "exportVersion": 1,
        "exportedAt": utcnow().isoformat(),
        "user": _row(user, "id", "display_name", "email", "is_guest", "preferences_json", "created_at"),
        "characters": [
            _row(
                c,
                "id",
                "name",
                "description",
                "category",
                "recipe_json",
                "version",
                "created_at",
                "updated_at",
                "deleted_at",
            )
            for c in chars
        ],
        "projects": [
            _row(p, "id", "title", "description", "status", "settings_json", "version", "created_at") for p in projects
        ],
        "scenes": [_row(s, "id", "project_id", "sequence_number", "scene_json") for s in scenes],
        "renders": [
            _row(r, "id", "project_id", "status", "progress_stage", "created_at", "completed_at") for r in renders
        ],
        "media": [_row(m, "id", "asset_type", "mime_type", "file_size", "created_at") for m in media],
    }


def delete_account(session: Session, storage: Any, user: User) -> None:
    """Hard-delete user content + stored media immediately; keep a tombstone user row and moderation/audit
    records (stripped of user content) for the published retention period."""
    for media in session.scalars(select(MediaAsset).where(MediaAsset.owner_user_id == user.id)):
        storage.delete(media.storage_key)
    char_ids = list(session.scalars(select(Character.id).where(Character.owner_user_id == user.id)))
    project_ids = list(session.scalars(select(Project.id).where(Project.owner_user_id == user.id)))
    session.execute(delete(CharacterLineage).where(CharacterLineage.character_id.in_(char_ids)))
    session.execute(delete(CharacterVersion).where(CharacterVersion.character_id.in_(char_ids)))
    session.execute(delete(RenderJob).where(RenderJob.owner_user_id == user.id))
    session.execute(delete(Scene).where(Scene.project_id.in_(project_ids)))
    session.execute(delete(Project).where(Project.owner_user_id == user.id))
    session.execute(delete(Mix).where(Mix.owner_user_id == user.id))
    session.execute(delete(Character).where(Character.owner_user_id == user.id))
    session.execute(delete(MediaAsset).where(MediaAsset.owner_user_id == user.id))
    session.execute(delete(Report).where(Report.reporter_user_id == user.id))
    session.add(AuditEvent(user_id=user.id, action="account.deleted", target_type="user", target_id=str(user.id)))
    _ = ModerationEvent  # moderation decisions retained (no content stored) per retention policy
    user.email = None
    user.display_name = "Deleted user"
    user.auth_provider_subject = f"deleted-{user.id}"
    user.preferences_json = {}
    user.deleted_at = utcnow()
    session.commit()

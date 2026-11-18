"""PostgreSQL-first ORM models (also run on SQLite for local tests).

UUID primary keys, timestamps, soft deletion where needed and explicit ownership (plan §9).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    auth_provider: Mapped[str] = mapped_column(String(32))
    auth_provider_subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str] = mapped_column(String(80))
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False)
    preferences_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("auth_provider", "auth_provider_subject", name="uq_user_subject"),)


class Licence(Base):
    __tablename__ = "licences"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    licence_url: Mapped[str] = mapped_column(String(500))
    terms_snapshot_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    commercial_use: Mapped[bool] = mapped_column(Boolean)
    attribution_required: Mapped[bool] = mapped_column(Boolean)
    redistribution: Mapped[bool] = mapped_column(Boolean, default=False)
    derivatives: Mapped[bool] = mapped_column(Boolean, default=False)
    review_status: Mapped[str] = mapped_column(String(32))
    reviewed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(120), nullable=True)


class AssetRegistryEntry(Base):
    __tablename__ = "asset_registry"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    asset_type: Mapped[str] = mapped_column(String(40), index=True)
    asset_version: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(120))
    storage_key: Mapped[str] = mapped_column(String(500))
    format: Mapped[str] = mapped_column(String(32))
    licence_id: Mapped[str] = mapped_column(ForeignKey("licences.id"))
    commercial_use_approved: Mapped[bool] = mapped_column(Boolean)
    provenance: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Character(Base):
    __tablename__ = "characters"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32))
    style: Mapped[str] = mapped_column(String(40))
    recipe_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    recipe_hash: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    preview_asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    thumbnail_asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    visibility: Mapped[str] = mapped_column(String(16), default="private")
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CharacterVersion(Base):
    __tablename__ = "character_versions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    character_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    recipe_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CharacterLineage(Base):
    __tablename__ = "character_lineage"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    character_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    # Not a FK: lineage survives deletion of a source character.
    source_character_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    contribution_weight: Mapped[float] = mapped_column(Float)
    mix_dimension: Mapped[str] = mapped_column(String(80))


class Mix(Base):
    __tablename__ = "mixes"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    result_character_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    request_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="draft")
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Scene(Base):
    __tablename__ = "scenes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    environment_asset_id: Mapped[str] = mapped_column(String(80))
    camera_preset_id: Mapped[str] = mapped_column(String(80))
    scene_json: Mapped[dict[str, Any]] = mapped_column(JSON)


class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(40))
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="ready")  # pending_upload | ready
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RenderJob(Base):
    __tablename__ = "render_jobs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="queued")
    progress_stage: Mapped[str] = mapped_column(String(32), default="queued")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    output_asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    thumbnail_asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    compute_ms: Mapped[int] = mapped_column(Integer, default=0)
    logs_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("owner_user_id", "idempotency_key", name="uq_render_idempotency"),)


class ModerationEvent(Base):
    __tablename__ = "moderation_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    content_type: Mapped[str] = mapped_column(String(40))
    content_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    decision: Mapped[str] = mapped_column(String(16))
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_version: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    reporter_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    content_type: Mapped[str] = mapped_column(String(40))
    content_id: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(40))
    details: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

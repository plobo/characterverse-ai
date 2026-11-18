from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

_DEV_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    """Runtime configuration. All values come from CV_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="CV_", env_file=".env", extra="ignore")

    env: str = "local"  # local | test | staging | production
    database_url: str = "sqlite:///./characterverse.db"
    jwt_secret: str = _DEV_SECRET
    signing_secret: str = _DEV_SECRET + "-signing"
    access_token_ttl_seconds: int = 3600
    signed_url_ttl_seconds: int = 900
    public_base_url: str = "http://localhost:8000"
    shared_dir: Path = REPO_ROOT / "shared"
    storage_dir: Path = Path("./var/storage")
    work_dir: Path = Path("./var/work")
    queue_backend: str = "thread"  # inline | thread | rq
    redis_url: str = "redis://localhost:6379/0"
    denylist_path: Path | None = None
    allow_dev_auth: bool = True

    render_fps: int = 24
    render_max_attempts: int = 3
    render_lease_seconds: int = 600
    render_backoff_base_seconds: float = 2.0
    render_backoff_cap_seconds: float = 60.0
    render_renderer: str = "procedural"  # procedural | blender

    rate_limit_generate_per_minute: int = 20
    max_active_renders_per_user: int = 3
    max_upload_bytes: int = 10 * 1024 * 1024
    temp_retention_hours: int = 24

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.env == "production":
            if self.jwt_secret.startswith("dev-only") or self.signing_secret.startswith("dev-only"):
                raise ValueError("CV_JWT_SECRET and CV_SIGNING_SECRET must be set in production")
            if self.allow_dev_auth:
                raise ValueError("CV_ALLOW_DEV_AUTH must be false in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

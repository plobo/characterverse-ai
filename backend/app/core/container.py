"""Dependency container wired once per process (API or worker)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings
from app.core.db import Database
from app.core.ratelimit import RateLimiter
from app.services.ai.mock_text import MockTextProvider
from app.services.catalog import Catalog
from app.services.moderation import DenyList, ImitationPatternClassifier, Moderator
from app.services.storage import LocalObjectStorage


@dataclass
class Container:
    settings: Settings
    db: Database
    catalog: Catalog
    storage: LocalObjectStorage
    moderator: Moderator
    text_provider: Any
    rate_limiter: RateLimiter
    queue: Any = None
    extras: dict[str, Any] = field(default_factory=dict)


def build_container(settings: Settings) -> Container:
    db = Database(settings.database_url)
    db.create_all()
    catalog = Catalog.from_manifest_files(settings.shared_dir)
    with db.session() as s:
        catalog.seed_registry(s)
        catalog.refresh_from_db(s)
    storage = LocalObjectStorage(settings.storage_dir, settings.signing_secret, settings.public_base_url)
    moderator = Moderator(DenyList.from_file(settings.denylist_path), ImitationPatternClassifier.default())
    container = Container(
        settings=settings,
        db=db,
        catalog=catalog,
        storage=storage,
        moderator=moderator,
        text_provider=MockTextProvider(),
        rate_limiter=RateLimiter(),
    )
    from app.workers.queue import build_queue

    container.queue = build_queue(container)
    return container

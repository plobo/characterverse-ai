"""RQ worker entrypoint: `rq worker renders` with CV_QUEUE_BACKEND=rq."""

from __future__ import annotations

import uuid
from functools import lru_cache

from app.core.config import get_settings
from app.core.container import build_container
from app.workers.render_worker import process_render_job


@lru_cache
def _container():
    return build_container(get_settings())


def run_job(job_id: str) -> str:
    return process_render_job(_container(), uuid.UUID(job_id))

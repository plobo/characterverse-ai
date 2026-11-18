"""Job queue adapters. Delivery is at-least-once; the worker's claim step makes duplicates harmless."""

from __future__ import annotations

import heapq
import logging
import threading
import time
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import or_, select

from app.core.db import utcnow
from app.domain.models import RenderJob

log = logging.getLogger("characterverse.queue")


class InlineQueue:
    """Synchronous queue for tests: runs jobs immediately (backoff delays are skipped)."""

    def __init__(self, container: Any, max_depth: int = 10):
        self.container = container
        self._depth = 0
        self.max_depth = max_depth
        self.delivered: list[uuid.UUID] = []

    def enqueue(self, job_id: uuid.UUID, delay: float = 0.0) -> None:
        from app.workers.render_worker import process_render_job

        self.delivered.append(job_id)
        if self._depth >= self.max_depth:
            return
        self._depth += 1
        try:
            if delay:
                with self.container.db.session() as s:  # pretend the delay elapsed
                    job = s.get(RenderJob, job_id)
                    if job:
                        job.next_attempt_at = None
                        s.commit()
            process_render_job(self.container, job_id)
        finally:
            self._depth -= 1


class ThreadQueue:
    """In-process scheduled queue for local development (no Redis required)."""

    def __init__(self, container: Any, workers: int = 1):
        self.container = container
        self._heap: list[tuple[float, int, uuid.UUID]] = []
        self._cv = threading.Condition()
        self._seq = 0
        self._stop = False
        self._threads = [threading.Thread(target=self._run, daemon=True, name=f"render-{i}") for i in range(workers)]
        for t in self._threads:
            t.start()

    def enqueue(self, job_id: uuid.UUID, delay: float = 0.0) -> None:
        with self._cv:
            self._seq += 1
            heapq.heappush(self._heap, (time.monotonic() + delay, self._seq, job_id))
            self._cv.notify()

    def _run(self) -> None:
        from app.workers.render_worker import process_render_job

        while True:
            with self._cv:
                while not self._stop and (not self._heap or self._heap[0][0] > time.monotonic()):
                    timeout = None if not self._heap else max(0.0, self._heap[0][0] - time.monotonic())
                    self._cv.wait(timeout)
                if self._stop:
                    return
                _, _, job_id = heapq.heappop(self._heap)
            try:
                process_render_job(self.container, job_id)
            except Exception:  # pragma: no cover - logged, job state stays durable in the DB
                log.exception("render job %s crashed", job_id)

    def stop(self) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify_all()


class RQQueue:
    """Redis/RQ adapter for staging & production. Worker entrypoint: app.workers.rq_entry.run_job."""

    def __init__(self, container: Any):
        from redis import Redis
        from rq import Queue

        self.queue = Queue("renders", connection=Redis.from_url(container.settings.redis_url))

    def enqueue(self, job_id: uuid.UUID, delay: float = 0.0) -> None:
        if delay > 0:
            self.queue.enqueue_in(
                timedelta(seconds=delay), "app.workers.rq_entry.run_job", str(job_id), job_timeout=1800
            )
        else:
            self.queue.enqueue("app.workers.rq_entry.run_job", str(job_id), job_timeout=1800)


def build_queue(container: Any):
    backend = container.settings.queue_backend
    if backend == "inline":
        return InlineQueue(container)
    if backend == "rq":
        return RQQueue(container)
    return ThreadQueue(container)


def recover_stranded_jobs(container: Any) -> list[uuid.UUID]:
    """On worker start: re-deliver queued jobs and processing jobs whose lease expired (worker crash)."""
    now = utcnow()
    with container.db.session() as s:
        ids = list(
            s.scalars(
                select(RenderJob.id).where(
                    or_(
                        RenderJob.status == "queued",
                        (RenderJob.status == "processing") & (RenderJob.lease_expires_at < now),
                    )
                )
            )
        )
    for job_id in ids:
        container.queue.enqueue(job_id)
    return ids


def cleanup_expired_temp(container: Any) -> int:
    """Delete temporary work directories older than the retention period."""
    root = container.settings.work_dir
    cutoff = time.time() - container.settings.temp_retention_hours * 3600
    removed = 0
    if not root.exists():
        return 0
    import shutil

    for child in root.iterdir():
        if child.is_dir() and child.stat().st_mtime < cutoff:
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    return removed

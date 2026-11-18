from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.errors import AppError


class RateLimiter:
    """In-process sliding-window limiter. Production deployments swap this for a Redis-backed limiter."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, user_key: str, bucket: str, limit: int, window_seconds: float = 60.0) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[(user_key, bucket)]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                raise AppError("RATE_LIMITED", f"Too many {bucket} requests; try again shortly")
            q.append(now)

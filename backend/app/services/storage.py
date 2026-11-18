"""Object storage behind an S3-like interface. Local filesystem adapter + HMAC signed URLs (plan §8.3).

Clients never receive storage credentials: every read/write goes through a short-lived signed URL.
An S3 adapter implements the same interface using presigned URLs (see docs/ADR/0006-object-storage.md).
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import quote

from app.core.errors import AppError
from app.core.security import sign, verify_signature

_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-./]{0,400}$")


class LocalObjectStorage:
    def __init__(self, root: Path, signing_secret: str, public_base_url: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.secret = signing_secret
        self.base = public_base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        if not _KEY_RE.match(key) or ".." in key:
            raise AppError("SIGNATURE_INVALID", "Invalid storage key")
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise AppError("SIGNATURE_INVALID", "Invalid storage key")
        return path

    def put(self, key: str, data: bytes) -> int:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(path)
        return len(data)

    def put_file(self, key: str, source: Path) -> int:
        return self.put(key, Path(source).read_bytes())

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def path_for(self, key: str) -> Path:
        return self._path(key)

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def delete_prefix(self, prefix: str) -> None:
        import shutil

        path = self._path(prefix)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)

    # ---- signed URLs ---------------------------------------------------
    def _message(self, method: str, key: str, exp: int) -> str:
        return f"{method.upper()}\n{key}\n{exp}"

    def signed_url(self, key: str, ttl_seconds: int, method: str = "GET", now: float | None = None) -> tuple[str, int]:
        exp = int((now or time.time()) + ttl_seconds)
        sig = sign(self.secret, self._message(method, key, exp))
        path = "upload" if method.upper() == "PUT" else "media"
        return f"{self.base}/v1/{path}/{quote(key)}?exp={exp}&sig={sig}", exp

    def verify(self, key: str, exp: int, sig: str, method: str = "GET", now: float | None = None) -> None:
        if not verify_signature(self.secret, self._message(method, key, exp), sig):
            raise AppError("SIGNATURE_INVALID", "Signature does not match")
        if (now or time.time()) > exp:
            raise AppError("SIGNATURE_EXPIRED", "Signed URL has expired")

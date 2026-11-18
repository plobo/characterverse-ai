from __future__ import annotations

import hashlib
import hmac
import time
import uuid

import jwt

from app.core.errors import AppError


def create_access_token(user_id: uuid.UUID, secret: str, ttl_seconds: int) -> tuple[str, int]:
    now = int(time.time())
    exp = now + ttl_seconds
    token = jwt.encode({"sub": str(user_id), "iat": now, "exp": exp, "typ": "access"}, secret, algorithm="HS256")
    return token, exp


def decode_access_token(token: str, secret: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.ExpiredSignatureError as exc:
        raise AppError("AUTH_INVALID", "Session expired") from exc
    except jwt.PyJWTError as exc:
        raise AppError("AUTH_INVALID", "Invalid session token") from exc
    if payload.get("typ") != "access":
        raise AppError("AUTH_INVALID", "Invalid session token")
    return uuid.UUID(payload["sub"])


def sign(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def verify_signature(secret: str, message: str, signature: str) -> bool:
    return hmac.compare_digest(sign(secret, message), signature)

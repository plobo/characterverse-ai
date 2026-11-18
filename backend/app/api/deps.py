from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.container import Container
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.domain.models import AuditEvent, ModerationEvent, User
from app.services.moderation import ModerationResult


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_session(container: Container = Depends(get_container)) -> Iterator[Session]:
    session = container.db.session()
    try:
        yield session
    finally:
        session.close()


def current_user(
    authorization: str | None = Header(default=None),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("AUTH_REQUIRED", "Sign in to continue")
    user_id = decode_access_token(authorization.split(" ", 1)[1].strip(), container.settings.jwt_secret)
    user = session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise AppError("AUTH_INVALID", "Account not found")
    return user


def parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise AppError("NOT_FOUND", "Not found") from exc


def get_owned(session: Session, model: Any, object_id: str, user: User) -> Any:
    """Ownership check on every read/write. Returns 404 (not 403) so IDs of other users do not leak."""
    obj = session.get(model, parse_uuid(object_id))
    if obj is None or getattr(obj, "owner_user_id", None) != user.id or getattr(obj, "deleted_at", None):
        raise AppError("NOT_FOUND", f"{model.__name__} not found")
    return obj


def audit(
    session: Session, user: User | None, action: str, target_type: str, target_id: Any = None, **metadata: Any
) -> None:
    session.add(
        AuditEvent(
            user_id=user.id if user else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            metadata_json=metadata,
        )
    )


FEEDBACK = {
    "PROTECTED_CHARACTER_REFERENCE": "This looks like it references an existing protected character. "
    "CharacterVerse only supports original characters.",
    "IMITATION_REQUEST": "Requests to copy or imitate existing characters, studios or franchises aren't allowed.",
    "POSSIBLE_IMITATION": "Tip: describe your own original idea rather than referencing existing works.",
}


def moderate(
    container: Container,
    session: Session,
    user: User | None,
    text: str,
    content_type: str,
    content_id: str | None = None,
) -> ModerationResult:
    result = container.moderator.check(text)
    session.add(
        ModerationEvent(
            user_id=user.id if user else None,
            content_type=content_type,
            content_id=content_id,
            decision=result.decision,
            reason_code=result.reason_code,
            policy_version=result.policy_version,
        )
    )
    session.commit()
    if result.blocked:
        raise AppError(
            "MODERATION_BLOCKED",
            FEEDBACK[result.reason_code or "IMITATION_REQUEST"],
            [
                {
                    "code": result.reason_code or "BLOCKED",
                    "field": content_type,
                    "message": "Content policy: original characters only",
                }
            ],
        )
    return result


def feedback_for(result: ModerationResult) -> dict[str, Any]:
    return {
        "decision": result.decision,
        "reasonCode": result.reason_code,
        "feedback": FEEDBACK.get(result.reason_code or ""),
    }


def rate_limit(container: Container, user: User, bucket: str) -> None:
    container.rate_limiter.check(str(user.id), bucket, container.settings.rate_limit_generate_per_minute)

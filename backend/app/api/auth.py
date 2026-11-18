from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import audit, current_user, get_container, get_session
from app.core.container import Container
from app.core.errors import AppError
from app.core.security import create_access_token, decode_access_token
from app.domain.models import Character, MediaAsset, Project, RenderJob, User
from app.schemas.api import RefreshRequest, SessionRequest, SessionResponse, UpdateMeRequest, UsageOut, UserOut
from app.services.export import delete_account, export_account

router = APIRouter(prefix="/v1", tags=["auth"])


def user_out(u: User) -> UserOut:
    return UserOut(
        id=str(u.id),
        display_name=u.display_name,
        email=u.email,
        is_guest=u.is_guest,
        preferences=u.preferences_json or {},
        created_at=u.created_at,
    )


@router.post("/auth/session", response_model=SessionResponse, response_model_by_alias=True)
def create_session(
    body: SessionRequest,
    request: Request,
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> SessionResponse:
    """Exchange an identity-provider token for an API session.

    * `oidc`: verifies an OIDC ID token (see ADR 0007; adapter configured per deployment).
    * `dev`: local/test only - `token` is used as the subject. Disabled in production.
    * `guest`: creates an anonymous account for local drafts.
    """
    throttle_client(container, request)
    if body.provider == "oidc":
        verifier = container.extras.get("oidc_verifier")
        if verifier is None:
            raise AppError("AUTH_INVALID", "OIDC provider is not configured on this server")
        subject, email, name = verifier(body.token)
    elif body.provider == "dev":
        if not container.settings.allow_dev_auth:
            raise AppError("AUTH_INVALID", "Developer sign-in is disabled")
        if not body.token:
            raise AppError("VALIDATION_FAILED", "token is required for dev sign-in")
        subject, email, name = body.token, body.email, body.display_name or body.token
    else:
        subject, email, name = f"guest-{uuid.uuid4()}", None, body.display_name or "Guest Creator"

    user = session.scalar(
        select(User).where(
            User.auth_provider == body.provider, User.auth_provider_subject == subject, User.deleted_at.is_(None)
        )
    )
    if user is None:
        user = User(
            auth_provider=body.provider,
            auth_provider_subject=subject,
            email=email,
            display_name=name[:80],
            is_guest=body.provider == "guest",
            preferences_json={},
        )
        session.add(user)
        session.flush()
        audit(session, user, "account.created", "user", user.id, provider=body.provider)
    session.commit()
    return issue_session(container, user)


def throttle_client(container: Container, request: Request) -> None:
    """Unauthenticated session creation is limited per client address (blocks guest-account quota farming)."""
    client_key = request.client.host if request.client else "unknown"
    container.rate_limiter.check(f"ip:{client_key}", "session", container.settings.rate_limit_sessions_per_minute)


def issue_session(container: Container, user: User) -> SessionResponse:
    st = container.settings
    token, exp = create_access_token(user.id, st.jwt_secret, st.access_token_ttl_seconds)
    refresh, rexp = create_access_token(user.id, st.jwt_secret, st.refresh_token_ttl_seconds, typ="refresh")
    return SessionResponse(
        access_token=token, expires_at=exp, refresh_token=refresh, refresh_expires_at=rexp, user=user_out(user)
    )


@router.post("/auth/refresh", response_model=SessionResponse)
def refresh_session(
    body: RefreshRequest,
    request: Request,
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> SessionResponse:
    """Exchange a long-lived refresh token for a new session (keeps guest accounts reachable)."""
    throttle_client(container, request)
    user = session.get(User, decode_access_token(body.refresh_token, container.settings.jwt_secret, typ="refresh"))
    if user is None or user.deleted_at is not None:
        raise AppError("AUTH_INVALID", "Account not found")
    return issue_session(container, user)


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(current_user)) -> UserOut:
    return user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(
    body: UpdateMeRequest, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> UserOut:
    user = session.merge(user)
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.preferences is not None:
        user.preferences_json = {**(user.preferences_json or {}), **body.preferences}
    session.commit()
    return user_out(user)


@router.get("/me/usage", response_model=UsageOut)
def usage(user: User = Depends(current_user), session: Session = Depends(get_session)) -> UsageOut:
    def count(model, *conds) -> int:
        return session.scalar(select(func.count()).select_from(model).where(model.owner_user_id == user.id, *conds))

    size = session.scalar(
        select(func.coalesce(func.sum(MediaAsset.file_size), 0)).where(MediaAsset.owner_user_id == user.id)
    )
    return UsageOut(
        characters=count(Character, Character.deleted_at.is_(None)),
        projects=count(Project, Project.deleted_at.is_(None)),
        renders=count(RenderJob),
        storage_bytes=int(size or 0),
    )


@router.get("/me/export")
def export_me(user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Machine-readable export of all account data (PIPEDA-style access request)."""
    return export_account(session, user)


@router.delete("/me", status_code=204)
def delete_me(
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    container: Container = Depends(get_container),
) -> Response:
    delete_account(session, container.storage, session.merge(user))
    return Response(status_code=204)

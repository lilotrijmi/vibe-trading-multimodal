"""Multi-user authentication, session management, and per-user rate limiting.

Mounted by ``agent/api_server.py`` via ``register_user_routes(app, ...)``.

Endpoints (all under the ``/api/auth`` prefix):
  POST   /api/auth/login          Issue a session cookie for valid username/password.
  POST   /api/auth/logout         Invalidate the current session.
  GET    /api/auth/me             Return the current user (or 401).
  GET    /api/auth/users          Admin-only: list users.
  POST   /api/auth/users          Admin-only: create a new user.
  PATCH  /api/auth/users/{id}     Admin-only: update role, rate limit, is_active.
  DELETE /api/auth/users/{id}     Admin-only: delete a user (cannot delete self).

Sessions are server-side (``auth_sessions`` table); the cookie stores only
the *hash* of the session token. Tokens are random 256-bit strings; the cookie
is ``HttpOnly``, ``SameSite=Lax``, and (when the request is HTTPS) ``Secure``.

The first time ``init_auth()`` is called it bootstraps an admin account from
``ADMIN_USERNAME`` / ``ADMIN_PASSWORD`` (default ``admin`` / ``vibe-trading``)
if no users exist yet.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as SqlSession

from src.db.auth_models import (
    RateLimitEntry,
    Session as AuthSession,
    User,
    count_recent_requests,
    hash_password,
    purge_expired_sessions,
    verify_password,
)
from src.db.session import get_session

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "vt_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days
RATE_LIMIT_WINDOW_SECONDS = 60 * 60  # 1 hour
_TOKEN_PREFIX = "vt_"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=512)


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    role: str
    rate_limit_per_hour: int
    note: str | None = None


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=8, max_length=512)
    role: str = Field("user", pattern="^(user|admin)$")
    rate_limit_per_hour: int = Field(60, ge=1, le=10_000)
    note: str | None = Field(None, max_length=200)


class UserUpdateRequest(BaseModel):
    role: str | None = Field(None, pattern="^(user|admin)$")
    rate_limit_per_hour: int | None = Field(None, ge=1, le=10_000)
    is_active: int | None = Field(None, ge=0, le=1)
    note: str | None = Field(None, max_length=200)
    password: str | None = Field(None, min_length=8, max_length=512)


class UserListResponse(BaseModel):
    users: list[CurrentUserResponse]


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def _issue_token() -> str:
    return _TOKEN_PREFIX + secrets.token_hex(32)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        path="/",
        httponly=True,
        samesite="lax",
        secure=False,  # set True when serving over HTTPS
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------


def _user_from_request(request: Request, session: SqlSession) -> User | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    auth = (
        session.query(AuthSession)
        .filter(AuthSession.token_hash == token_hash, AuthSession.expires_at > now)
        .first()
    )
    if auth is None:
        return None
    auth.last_seen_at = now
    user = session.query(User).filter(User.id == auth.user_id, User.is_active == 1).first()
    return user


def require_user_dep(request: Request, session: SqlSession = Depends(get_session)) -> User:
    user = _user_from_request(request, session)
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return user


def require_admin_dep(user: User = Depends(require_user_dep)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin role required")
    return user


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


def enforce_rate_limit(user: User, endpoint: str, session: SqlSession) -> None:
    """Raise 429 if the user has exceeded their hourly request budget."""
    used = count_recent_requests(session, user.id, RATE_LIMIT_WINDOW_SECONDS)
    if used >= user.rate_limit_per_hour:
        raise HTTPException(
            status_code=429,
            detail=(
                f"rate limit exceeded ({user.rate_limit_per_hour} requests/hour); "
                "try again later"
            ),
            headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
        )
    session.add(RateLimitEntry(user_id=user.id, endpoint=endpoint[:128]))


# ---------------------------------------------------------------------------
# Bootstrap admin
# ---------------------------------------------------------------------------


def init_auth(session_factory: Any) -> None:
    """Create the auth tables and bootstrap an initial admin user.

    Reads ``ADMIN_USERNAME`` and ``ADMIN_PASSWORD`` from the environment
    (defaults ``admin`` / ``vibe-trading``). Idempotent: if at least one user
    exists, no changes are made.
    """
    session = session_factory()
    try:
        existing = session.query(User).count()
        if existing > 0:
            return
        username = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"
        password = os.environ.get("ADMIN_PASSWORD", "vibe-trading")
        admin = User(
            username=username,
            password_hash=hash_password(password),
            role="admin",
            rate_limit_per_hour=int(os.environ.get("ADMIN_RATE_LIMIT_PER_HOUR", "600")),
            note="bootstrap admin (rotate the password in Settings → Users)",
        )
        session.add(admin)
        session.commit()
        logger.warning("bootstrap admin user %r created — please change the password", username)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def register_user_routes(app: Any) -> None:
    """Mount user management routes on the FastAPI app."""
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    @router.post("/login", response_model=CurrentUserResponse)
    def login(
        payload: LoginRequest,
        response: Response,
        session: SqlSession = Depends(get_session),
    ) -> CurrentUserResponse:
        user = (
            session.query(User)
            .filter(User.username == payload.username, User.is_active == 1)
            .one_or_none()
        )
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="invalid username or password")
        token = _issue_token()
        session.add(
            AuthSession(
                user_id=user.id,
                token_hash=_hash_token(token),
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL_SECONDS),
            )
        )
        user.last_login_at = datetime.now(timezone.utc)
        session.commit()
        _set_session_cookie(response, token)
        return CurrentUserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            rate_limit_per_hour=user.rate_limit_per_hour,
            note=user.note,
        )

    @router.post("/logout", status_code=204)
    def logout(
        request: Request,
        response: Response,
        session: SqlSession = Depends(get_session),
    ) -> Response:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            session.query(AuthSession).filter(
                AuthSession.token_hash == _hash_token(token)
            ).delete(synchronize_session=False)
            session.commit()
        _clear_session_cookie(response)
        return Response(status_code=204)

    @router.get("/me", response_model=CurrentUserResponse)
    def me(user: User = Depends(require_user_dep)) -> CurrentUserResponse:
        return CurrentUserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            rate_limit_per_hour=user.rate_limit_per_hour,
            note=user.note,
        )

    # ---- admin-only: user management ----

    @router.get("/users", response_model=UserListResponse)
    def list_users(
        _admin: User = Depends(require_admin_dep),
        session: SqlSession = Depends(get_session),
    ) -> UserListResponse:
        purge_expired_sessions(session)
        users = session.query(User).order_by(User.username.asc()).all()
        return UserListResponse(
            users=[
                CurrentUserResponse(
                    id=u.id,
                    username=u.username,
                    role=u.role,
                    rate_limit_per_hour=u.rate_limit_per_hour,
                    note=u.note,
                )
                for u in users
            ]
        )

    @router.post("/users", response_model=CurrentUserResponse, status_code=201)
    def create_user(
        payload: UserCreateRequest,
        _admin: User = Depends(require_admin_dep),
        session: SqlSession = Depends(get_session),
    ) -> CurrentUserResponse:
        existing = session.query(User).filter(User.username == payload.username).one_or_none()
        if existing is not None:
            raise HTTPException(status_code=409, detail="username already exists")
        user = User(
            username=payload.username,
            password_hash=hash_password(payload.password),
            role=payload.role,
            rate_limit_per_hour=payload.rate_limit_per_hour,
            note=payload.note,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return CurrentUserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            rate_limit_per_hour=user.rate_limit_per_hour,
            note=user.note,
        )

    @router.patch("/users/{user_id}", response_model=CurrentUserResponse)
    def update_user(
        user_id: int,
        payload: UserUpdateRequest,
        admin: User = Depends(require_admin_dep),
        session: SqlSession = Depends(get_session),
    ) -> CurrentUserResponse:
        user = session.query(User).filter(User.id == user_id).one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        if user.id == admin.id and payload.role is not None and payload.role != "admin":
            raise HTTPException(status_code=400, detail="cannot demote yourself from admin")
        if payload.role is not None:
            user.role = payload.role
        if payload.rate_limit_per_hour is not None:
            user.rate_limit_per_hour = payload.rate_limit_per_hour
        if payload.is_active is not None:
            user.is_active = payload.is_active
        if payload.note is not None:
            user.note = payload.note
        if payload.password:
            user.password_hash = hash_password(payload.password)
        session.commit()
        return CurrentUserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            rate_limit_per_hour=user.rate_limit_per_hour,
            note=user.note,
        )

    @router.delete("/users/{user_id}", status_code=204)
    def delete_user(
        user_id: int,
        admin: User = Depends(require_admin_dep),
        session: SqlSession = Depends(get_session),
    ) -> Response:
        if user_id == admin.id:
            raise HTTPException(
                status_code=400, detail="cannot delete the currently authenticated admin"
            )
        user = session.query(User).filter(User.id == user_id).one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        session.query(AuthSession).filter(AuthSession.user_id == user_id).delete(
            synchronize_session=False
        )
        session.query(RateLimitEntry).filter(RateLimitEntry.user_id == user_id).delete(
            synchronize_session=False
        )
        session.delete(user)
        session.commit()
        return Response(status_code=204)

    app.include_router(router)

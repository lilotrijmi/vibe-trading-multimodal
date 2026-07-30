"""Auth models: User, Session, RateLimitEntry.

The base ``src.db.models.Base`` is reused so all tables live in the same
SQLite database (``vibe_trading.db``). Users authenticate with a username +
password (hashed with PBKDF2-HMAC-SHA256 + salt). Sessions are stored as
opaque random tokens in the ``sessions`` table and tracked in the user's
browser via a ``HttpOnly`` cookie. The ``rate_limit_log`` table provides a
sliding-window per-user request counter (one row per request, pruned on read).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Session as SqlSession

from src.db.models import Base


# PBKDF2-HMAC-SHA256 from the stdlib. Iteration count is high enough to make
# brute force expensive (~250k rounds on modern CPUs).
_PBKDF2_ITERATIONS = 260_000
_PBKDF2_ALGO = "sha256"
_SALT_BYTES = 16


def hash_password(plaintext: str) -> str:
    """Return a self-describing password hash: ``pbkdf2_sha256$<iters>$<salt-hex>$<hash-hex>``."""
    import hashlib
    import os

    if not plaintext:
        raise ValueError("password must not be empty")
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, plaintext.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_{_PBKDF2_ALGO}${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(plaintext: str, encoded: str) -> bool:
    """Constant-time comparison of a plaintext against an encoded hash."""
    import hashlib
    import hmac

    try:
        algo_part, iters_part, salt_hex, hash_hex = encoded.split("$", 3)
    except ValueError:
        return False
    if not algo_part.startswith("pbkdf2_"):
        return False
    algo = algo_part.split("_", 1)[1]
    try:
        iters = int(iters_part)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(hash_hex)
    candidate = hashlib.pbkdf2_hmac(algo, plaintext.encode("utf-8"), salt, iters)
    return hmac.compare_digest(candidate, expected)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), nullable=False, default="user")  # "user" or "admin"
    rate_limit_per_hour = Column(Integer, nullable=False, default=60)
    is_active = Column(Integer, nullable=False, default=1)  # 1 = active, 0 = disabled
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime, nullable=True)


class Session(Base):
    __tablename__ = "auth_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)


class RateLimitEntry(Base):
    __tablename__ = "rate_limit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    endpoint = Column(String(128), nullable=False)
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


Index("ix_rate_limit_user_ts", RateLimitEntry.user_id, RateLimitEntry.ts)


def purge_expired_sessions(session: SqlSession, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    deleted = session.query(Session).filter(Session.expires_at < now).delete(synchronize_session=False)
    return int(deleted or 0)


def count_recent_requests(
    session: SqlSession,
    user_id: int,
    window_seconds: int,
    now: datetime | None = None,
) -> int:
    from datetime import timedelta

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window_seconds)
    return int(
        session.query(RateLimitEntry)
        .filter(RateLimitEntry.user_id == user_id, RateLimitEntry.ts >= cutoff)
        .count()
    )

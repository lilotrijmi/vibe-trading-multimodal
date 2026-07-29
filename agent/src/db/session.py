"""Database session factory."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Base

logger = logging.getLogger(__name__)


_engine = None
_SessionLocal: sessionmaker | None = None


def init_db(db_path: Path) -> None:
    """Initialize database engine and create tables.

    Creates the parent directory if missing. If the file itself is not writable
    (e.g. due to a read-only volume mount or a permissions mismatch), raises
    a clear ``RuntimeError`` rather than the underlying ``sqlite3`` error.
    """
    global _engine, _SessionLocal
    db_path = Path(db_path)
    parent = db_path.parent.resolve()
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Cannot create database directory {parent}: {exc}"
        ) from exc

    # Touch the file so we surface a clear "directory not writable" error
    # before SQLAlchemy tries to open it.
    try:
        if not db_path.exists():
            db_path.touch(mode=0o600)
    except OSError as exc:
        raise RuntimeError(
            f"Cannot create database file {db_path} "
            f"(is the volume mounted and writable?): {exc}"
        ) from exc

    logger.info("db init: %s", db_path)
    _engine = create_engine(
        f"sqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(_engine)


def get_session() -> Session:
    """Get a new database session."""
    if _SessionLocal is None:
        raise RuntimeError("DB not initialized; call init_db() first")
    return _SessionLocal()

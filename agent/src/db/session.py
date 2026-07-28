"""Database session factory."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Base


_engine = None
_SessionLocal: sessionmaker | None = None


def init_db(db_path: Path) -> None:
    """Initialize database engine and create tables."""
    global _engine, _SessionLocal
    db_path.parent.mkdir(parents=True, exist_ok=True)
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

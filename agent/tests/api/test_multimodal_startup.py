"""Tests for multimodal subsystem startup storage policy."""

from pathlib import Path

import pytest

from src.api import multimodal_startup
from src.db import session as db_session


def test_explicit_unwritable_db_path_fails_instead_of_falling_back_to_tmp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit database path must never silently become ephemeral."""
    configured_db = tmp_path / "unwritable" / "configured.db"
    storage_dir = tmp_path / "storage"

    monkeypatch.setenv("VIBE_TRADING_DB_PATH", str(configured_db))
    monkeypatch.setenv("MULTIMODAL_STORAGE_DIR", str(storage_dir))
    monkeypatch.setattr(
        multimodal_startup,
        "_is_writable_dir",
        lambda path: path != configured_db.parent,
    )

    with pytest.raises(RuntimeError, match="VIBE_TRADING_DB_PATH"):
        multimodal_startup.init_multimodal_subsystem()


def test_init_db_wraps_sqlite_initialization_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SQLite open and WAL errors include the configured database path."""
    db_path = tmp_path / "configured.db"

    class FailingMetadata:
        @staticmethod
        def create_all(_engine: object) -> None:
            raise OSError("database is read-only")

    monkeypatch.setattr(db_session.Base, "metadata", FailingMetadata())

    with pytest.raises(RuntimeError, match=str(db_path).replace("\\", "\\\\")):
        db_session.init_db(db_path)

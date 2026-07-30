"""Tests for multi-user auth + per-user rate limiting."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.user_routes import (
    init_auth,
    register_user_routes,
    SESSION_COOKIE_NAME,
)
from src.db.auth_models import (
    RateLimitEntry,
    Session as AuthSession,
    User,
    hash_password,
    verify_password,
)
from src.db.session import init_db, get_session


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "auth_test.db"
    init_db(db_path)
    init_auth(get_session)
    app = FastAPI()
    register_user_routes(app)
    return TestClient(app)


def test_password_hash_roundtrip() -> None:
    encoded = hash_password("hunter2-correct")
    assert verify_password("hunter2-correct", encoded) is True
    assert verify_password("hunter2-WRONG", encoded) is False


def test_bootstrap_admin_created_when_no_users(tmp_path: Path) -> None:
    db_path = tmp_path / "bootstrap_test.db"
    init_db(db_path)
    init_auth(get_session)
    session = get_session()
    try:
        admin = session.query(User).filter(User.username == "admin").one_or_none()
        assert admin is not None
        assert admin.role == "admin"
        assert verify_password("vibe-trading", admin.password_hash) is True
    finally:
        session.close()


def test_bootstrap_admin_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "idem_test.db"
    init_db(db_path)
    init_auth(get_session)
    init_auth(get_session)
    init_auth(get_session)
    session = get_session()
    try:
        assert session.query(User).count() == 1
    finally:
        session.close()


def test_login_with_default_admin(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "vibe-trading"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    # Session cookie set.
    assert SESSION_COOKIE_NAME in response.cookies


def test_login_rejects_bad_password(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "WRONG"},
    )
    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient) -> None:
    client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "vibe-trading"},
    )
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["username"] == "admin"


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_admin_can_create_user(client: TestClient) -> None:
    client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "vibe-trading"},
    )
    response = client.post(
        "/api/auth/users",
        json={
            "username": "friend",
            "password": "friendpassword",
            "role": "user",
            "rate_limit_per_hour": 30,
        },
    )
    assert response.status_code == 201
    assert response.json()["username"] == "friend"


def test_non_admin_cannot_create_user(client: TestClient) -> None:
    # Create a non-admin user first via the admin, then login as that user.
    client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "vibe-trading"},
    )
    client.post(
        "/api/auth/users",
        json={"username": "friend", "password": "friendpassword", "role": "user"},
    )
    client.post("/api/auth/logout")

    client.post(
        "/api/auth/login",
        json={"username": "friend", "password": "friendpassword"},
    )
    response = client.post(
        "/api/auth/users",
        json={"username": "intruder", "password": "abcdefgh"},
    )
    assert response.status_code == 403


def test_admin_can_list_users(client: TestClient) -> None:
    client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "vibe-trading"},
    )
    response = client.get("/api/auth/users")
    assert response.status_code == 200
    users = response.json()["users"]
    assert any(u["username"] == "admin" for u in users)


def test_admin_can_delete_user(client: TestClient) -> None:
    client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "vibe-trading"},
    )
    create = client.post(
        "/api/auth/users",
        json={"username": "victim", "password": "victimpass"},
    )
    victim_id = create.json()["id"]

    response = client.delete(f"/api/auth/users/{victim_id}")
    assert response.status_code == 204


def test_admin_cannot_delete_self(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "vibe-trading"},
    )
    assert response.status_code == 200
    me = client.get("/api/auth/me").json()
    admin_id = me["id"]
    response = client.delete(f"/api/auth/users/{admin_id}")
    assert response.status_code == 400


def test_logout_clears_session(client: TestClient) -> None:
    client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "vibe-trading"},
    )
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    # After logout, /me should fail.
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_duplicate_username_rejected(client: TestClient) -> None:
    client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "vibe-trading"},
    )
    response = client.post(
        "/api/auth/users",
        json={"username": "admin", "password": "different"},
    )
    assert response.status_code == 409

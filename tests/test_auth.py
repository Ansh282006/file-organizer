"""Tests for password protection."""

import pytest

from fastapi.testclient import TestClient

import auth


# ---------- password hashing ----------

def test_hash_and_verify_roundtrip():
    h = auth.hash_password("hunter2secret")
    assert auth.verify_password("hunter2secret", h)
    assert not auth.verify_password("wrong", h)
    assert not auth.verify_password("", h)


def test_hash_uses_random_salt():
    h1 = auth.hash_password("same")
    h2 = auth.hash_password("same")
    assert h1 != h2
    assert "$" in h1


def test_verify_rejects_malformed():
    assert not auth.verify_password("x", "")
    assert not auth.verify_password("x", "no-dollar-sign")


def test_empty_password_rejected():
    with pytest.raises(ValueError):
        auth.hash_password("")


# ---------- sessions ----------

def test_session_roundtrip():
    token = auth.create_session()
    assert auth.verify_session(token)


def test_session_rejects_garbage():
    assert not auth.verify_session("")
    assert not auth.verify_session("not-a-real-token")


# ---------- is_public_path ----------

def test_is_public_path_health():
    assert auth.is_public_path("/api/health")


def test_is_public_path_auth_endpoints():
    assert auth.is_public_path("/api/auth/status")
    assert auth.is_public_path("/api/auth/login")
    assert auth.is_public_path("/api/auth/logout")


def test_is_public_path_static():
    assert auth.is_public_path("/")
    assert auth.is_public_path("/style.css")
    assert auth.is_public_path("/app.js")


def test_is_public_path_protected():
    assert not auth.is_public_path("/api/scan")
    assert not auth.is_public_path("/api/rules")
    assert not auth.is_public_path("/api/settings")


# ---------- End-to-end via TestClient ----------

@pytest.fixture
def client_with_fresh_auth(app_client):
    """Ensure auth is disabled at the start of each test."""
    app_client.post("/api/settings", json={"password": "", "auth_enabled": False})
    yield app_client
    app_client.post("/api/settings", json={"password": "", "auth_enabled": False})


def test_auth_status_when_disabled(client_with_fresh_auth):
    r = client_with_fresh_auth.get("/api/auth/status")
    assert r.status_code == 200
    body = r.json()
    assert body["required"] is False
    assert body["authenticated"] is True


def test_all_endpoints_open_when_auth_disabled(client_with_fresh_auth):
    # No cookie → should still work
    r = client_with_fresh_auth.get("/api/rules")
    assert r.status_code == 200


def test_setting_password_enables_auth(client_with_fresh_auth):
    r = client_with_fresh_auth.post("/api/settings", json={"password": "hunter2secret"})
    assert r.status_code == 200

    r = client_with_fresh_auth.get("/api/auth/status")
    assert r.json()["required"] is True


def test_password_too_short_rejected(client_with_fresh_auth):
    r = client_with_fresh_auth.post("/api/settings", json={"password": "abc"})
    assert r.status_code == 400


def test_protected_endpoint_requires_login(client_with_fresh_auth):
    client_with_fresh_auth.post("/api/settings", json={"password": "hunter2secret"})

    # Not logged in → 401
    r = client_with_fresh_auth.get("/api/rules")
    assert r.status_code == 401


def test_login_with_wrong_password_fails(client_with_fresh_auth):
    client_with_fresh_auth.post("/api/settings", json={"password": "hunter2secret"})

    r = client_with_fresh_auth.post("/api/auth/login", json={"password": "wrong"})
    assert r.status_code == 401


def test_login_then_access(client_with_fresh_auth):
    client_with_fresh_auth.post("/api/settings", json={"password": "hunter2secret"})

    r = client_with_fresh_auth.post("/api/auth/login", json={"password": "hunter2secret"})
    assert r.status_code == 200

    # Now authenticated
    r = client_with_fresh_auth.get("/api/rules")
    assert r.status_code == 200


def test_logout_clears_session(client_with_fresh_auth):
    client_with_fresh_auth.post("/api/settings", json={"password": "hunter2secret"})
    client_with_fresh_auth.post("/api/auth/login", json={"password": "hunter2secret"})
    assert client_with_fresh_auth.get("/api/rules").status_code == 200

    client_with_fresh_auth.post("/api/auth/logout")
    assert client_with_fresh_auth.get("/api/rules").status_code == 401


def test_health_always_public(client_with_fresh_auth):
    client_with_fresh_auth.post("/api/settings", json={"password": "hunter2secret"})
    r = client_with_fresh_auth.get("/api/health")
    assert r.status_code == 200


def test_clearing_password_disables_auth(client_with_fresh_auth):
    client_with_fresh_auth.post("/api/settings", json={"password": "hunter2secret"})
    assert client_with_fresh_auth.get("/api/rules").status_code == 401

    # Still-authenticated request to clear password (or log in first)
    client_with_fresh_auth.post("/api/auth/login", json={"password": "hunter2secret"})
    client_with_fresh_auth.post("/api/settings", json={"password": ""})

    # Fresh client sees auth disabled
    assert client_with_fresh_auth.get("/api/auth/status").json()["required"] is False
    assert client_with_fresh_auth.get("/api/rules").status_code == 200
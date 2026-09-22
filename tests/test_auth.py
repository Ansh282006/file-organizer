"""Tests for password protection and session persistence."""

import pytest
from fastapi.testclient import TestClient

import auth


# ============================================================
# Password hashing
# ============================================================

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


# ============================================================
# Session tokens
# ============================================================

def test_session_roundtrip():
    token = auth.create_session()
    assert auth.verify_session(token)


def test_session_rejects_garbage():
    assert not auth.verify_session("")
    assert not auth.verify_session("not-a-real-token")


# ============================================================
# is_public_path
# ============================================================

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


# ============================================================
# End-to-end via TestClient
# ============================================================

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

    # Log in first, then clear
    client_with_fresh_auth.post("/api/auth/login", json={"password": "hunter2secret"})
    client_with_fresh_auth.post("/api/settings", json={"password": ""})

    # Fresh request — auth disabled
    assert client_with_fresh_auth.get("/api/auth/status").json()["required"] is False
    assert client_with_fresh_auth.get("/api/rules").status_code == 200


# ============================================================
# Session secret persistence (Step 27)
# ============================================================

def test_session_secret_persists_across_load(app_client):
    """Sessions must survive a settings reload."""
    import settings as settings_mod

    # Trigger a settings write by setting a password
    app_client.post("/api/settings", json={"password": "hunter2secret"})

    s1 = settings_mod.load_settings()
    assert s1.session_secret
    secret1 = s1.session_secret

    # Reload from disk — secret should be identical
    s2 = settings_mod.load_settings()
    assert s2.session_secret == secret1

    # Clean up
    app_client.post("/api/auth/login", json={"password": "hunter2secret"})
    app_client.post("/api/settings", json={"password": ""})


def test_password_change_rotates_secret(app_client):
    """Changing the password must invalidate existing sessions."""
    import settings as settings_mod

    app_client.post("/api/settings", json={"password": "hunter2secret"})
    secret1 = settings_mod.load_settings().session_secret

    app_client.post("/api/auth/login", json={"password": "hunter2secret"})
    app_client.post("/api/settings", json={"password": "newpassword123"})
    secret2 = settings_mod.load_settings().session_secret

    assert secret1 != secret2

    # Old cookie no longer works — log out and confirm
    app_client.post("/api/auth/logout")
    r = app_client.get("/api/rules")
    assert r.status_code == 401

    # New password works
    r = app_client.post("/api/auth/login", json={"password": "newpassword123"})
    assert r.status_code == 200

    # Clean up
    app_client.post("/api/settings", json={"password": ""})


def test_secret_never_leaks_to_frontend(app_client):
    """/api/settings must not expose session_secret or password_hash."""
    app_client.post("/api/settings", json={"password": "hunter2secret"})
    app_client.post("/api/auth/login", json={"password": "hunter2secret"})

    r = app_client.get("/api/settings")
    s = r.json()["settings"]
    assert s["password_hash"] == ""
    assert s["session_secret"] == ""
    assert s["has_password"] is True

    # Clean up
    app_client.post("/api/settings", json={"password": ""})


def test_secret_persists_between_test_client_sessions(tmp_path):
    """A fresh TestClient should accept a cookie issued by an earlier one."""
    from fastapi.testclient import TestClient
    import app as app_module

    cookie_value = None

    # First client — log in
    with TestClient(app_module.app) as c1:
        c1.post("/api/settings", json={"password": "hunter2secret"})
        r = c1.post("/api/auth/login", json={"password": "hunter2secret"})
        assert r.status_code == 200
        cookie_value = c1.cookies.get("fo_session")
        assert cookie_value

    # Second client — reuse the cookie
    with TestClient(app_module.app) as c2:
        c2.cookies.set("fo_session", cookie_value)
        r = c2.get("/api/rules")
        assert r.status_code == 200

        # Clean up
        c2.post("/api/settings", json={"password": ""})
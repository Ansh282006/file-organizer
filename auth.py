"""Optional password protection.

- Password is stored as PBKDF2-HMAC-SHA256(salt, password) hex in settings.
- Sessions are signed cookies (itsdangerous), verified per request.
- Session store is in-memory only — restart the app to invalidate all sessions.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

from itsdangerous import BadSignature, URLSafeTimedSerializer


COOKIE_NAME = "fo_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7   # 7 days
PBKDF2_ITERATIONS = 200_000


# ---------- password hashing ----------

def hash_password(password: str, salt: str | None = None) -> str:
    """Return 'salt$hash' (both hex). If salt is None, generate one."""
    if not password:
        raise ValueError("Password cannot be empty")
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time compare against a stored 'salt$hash' string."""
    if not password or not stored or "$" not in stored:
        return False
    salt, expected = stored.split("$", 1)
    try:
        candidate = hash_password(password, salt=salt).split("$", 1)[1]
    except ValueError:
        return False
    return hmac.compare_digest(candidate, expected)


# ---------- session tokens ----------

def _secret() -> str:
    """Stable secret for signing cookies — regenerated each process start.
    Persisting this would let sessions survive a restart, but that adds
    a settings field. For now: restart = everyone logged out."""
    if not hasattr(_secret, "_cached"):
        _secret._cached = secrets.token_urlsafe(32)  # type: ignore[attr-defined]
    return _secret._cached  # type: ignore[attr-defined]


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret(), salt="file-organizer-session")


def create_session() -> str:
    return _serializer().dumps({"t": int(time.time())})


def verify_session(token: str) -> bool:
    if not token:
        return False
    try:
        _serializer().loads(token, max_age=SESSION_MAX_AGE)
        return True
    except (BadSignature, Exception):
        return False


# ---------- FastAPI helpers ----------

def is_auth_required() -> bool:
    """True if a password is set."""
    from settings import load_settings
    s = load_settings()
    return bool(s.auth_enabled and s.password_hash)


def is_public_path(path: str) -> bool:
    """Paths that never require auth."""
    if path == "/api/health":
        return True
    if path.startswith("/api/auth/"):
        return True
    # Static assets and the root — the frontend needs to load the login UI
    if not path.startswith("/api/"):
        return True
    return False


def is_authenticated(cookies: dict) -> bool:
    token = cookies.get(COOKIE_NAME, "")
    return verify_session(token)
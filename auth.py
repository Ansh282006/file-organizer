"""Optional password protection.

- Password is stored as PBKDF2-HMAC-SHA256(salt, password) hex in settings.
- Sessions are signed cookies (itsdangerous), verified per request.
- The signing secret is persisted in settings.yaml, so sessions survive
  server restarts. It rotates automatically when the password changes.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

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
    """Stable secret for signing cookies — persisted in settings.yaml."""
    from settings import load_settings
    s = load_settings()
    if not s.session_secret:
        # Should not happen — load_settings guarantees a value — but be safe
        s.session_secret = secrets.token_urlsafe(32)
        from settings import save_settings
        try:
            save_settings(s)
        except OSError:
            pass
    return s.session_secret


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
    except BadSignature:
        return False
    except Exception:
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
    if not path.startswith("/api/"):
        return True
    return False


def is_authenticated(cookies: dict) -> bool:
    token = cookies.get(COOKIE_NAME, "")
    return verify_session(token)
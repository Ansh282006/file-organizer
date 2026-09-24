"""Persistent settings for the file organizer."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml

from paths import SETTINGS_FILE


DEFAULT_SKIP_NAMES = [".DS_Store", "Thumbs.db", "desktop.ini"]
DEFAULT_SKIP_PREFIXES = ["."]

DATE_FORMAT_OPTIONS = [
    {"value": "%Y-%m",     "label": "2026-09  (year-month)"},
    {"value": "%Y-%m-%d",  "label": "2026-09-22  (year-month-day)"},
    {"value": "%Y",        "label": "2026  (year only)"},
    {"value": "%m-%Y",     "label": "09-2026  (month-year)"},
]


@dataclass
class Settings:
    default_mode: str = "extension"
    date_format: str = "%Y-%m"
    skip_names: list[str] = field(default_factory=lambda: list(DEFAULT_SKIP_NAMES))
    skip_prefixes: list[str] = field(default_factory=lambda: list(DEFAULT_SKIP_PREFIXES))
    auth_enabled: bool = False
    password_hash: str = ""
    session_secret: str = ""
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    backup_keep_count: int = 30

    def to_dict(self, hide_secrets: bool = False) -> dict:
        data = asdict(self)
        if hide_secrets:
            data["password_hash"] = ""
            data["session_secret"] = ""
            data["has_password"] = bool(self.password_hash)
        return data


def load_settings(path: Path | None = None) -> Settings:
    path = path or SETTINGS_FILE
    if not path.exists():
        s = Settings()
        save_settings(s, path)
        return s
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return Settings()

    s = Settings(
        default_mode=raw.get("default_mode", "extension"),
        date_format=raw.get("date_format", "%Y-%m"),
        skip_names=list(raw.get("skip_names", DEFAULT_SKIP_NAMES)),
        skip_prefixes=list(raw.get("skip_prefixes", DEFAULT_SKIP_PREFIXES)),
        auth_enabled=bool(raw.get("auth_enabled", False)),
        password_hash=str(raw.get("password_hash", "") or ""),
        session_secret=str(raw.get("session_secret", "") or ""),
        backup_enabled=bool(raw.get("backup_enabled", True)),
        backup_interval_hours=int(raw.get("backup_interval_hours", 24)),
        backup_keep_count=int(raw.get("backup_keep_count", 30)),
    )

    if not s.session_secret:
        s.session_secret = secrets.token_urlsafe(32)
        try:
            save_settings(s, path)
        except OSError:
            pass

    return s


def save_settings(settings: Settings, path: Path | None = None) -> None:
    path = path or SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(settings.to_dict(), sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def update_settings(partial: dict, path: Path | None = None) -> Settings:
    from auth import hash_password

    current = load_settings(path)
    data = current.to_dict()

    if "default_mode" in partial:
        mode = str(partial["default_mode"]).strip()
        if mode not in {"extension", "date"}:
            raise ValueError(f"Invalid default_mode: {mode}")
        data["default_mode"] = mode

    if "date_format" in partial:
        fmt = str(partial["date_format"]).strip()
        if not fmt:
            raise ValueError("date_format cannot be empty")
        data["date_format"] = fmt

    if "skip_names" in partial:
        names = partial["skip_names"]
        if not isinstance(names, list):
            raise ValueError("skip_names must be a list")
        data["skip_names"] = [str(n).strip() for n in names if str(n).strip()]

    if "skip_prefixes" in partial:
        prefixes = partial["skip_prefixes"]
        if not isinstance(prefixes, list):
            raise ValueError("skip_prefixes must be a list")
        data["skip_prefixes"] = [str(p) for p in prefixes if str(p)]

    if "auth_enabled" in partial:
        data["auth_enabled"] = bool(partial["auth_enabled"])

    if "password" in partial:
        pw = partial.get("password")
        if pw is None or pw == "":
            data["password_hash"] = ""
            data["auth_enabled"] = False
            data["session_secret"] = secrets.token_urlsafe(32)
        else:
            pw = str(pw)
            if len(pw) < 6:
                raise ValueError("Password must be at least 6 characters")
            data["password_hash"] = hash_password(pw)
            if "auth_enabled" not in partial:
                data["auth_enabled"] = True
            data["session_secret"] = secrets.token_urlsafe(32)

    if "backup_enabled" in partial:
        data["backup_enabled"] = bool(partial["backup_enabled"])

    if "backup_interval_hours" in partial:
        v = int(partial["backup_interval_hours"])
        if v < 1:
            raise ValueError("backup_interval_hours must be >= 1")
        data["backup_interval_hours"] = v

    if "backup_keep_count" in partial:
        v = int(partial["backup_keep_count"])
        if v < 1:
            raise ValueError("backup_keep_count must be >= 1")
        data["backup_keep_count"] = v

    updated = Settings(**data)
    save_settings(updated, path)
    return updated
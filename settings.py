"""Persistent settings for the file organizer."""

from __future__ import annotations

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

    def to_dict(self) -> dict:
        return asdict(self)


def load_settings(path: Path | None = None) -> Settings:
    path = path or SETTINGS_FILE
    if not path.exists():
        return Settings()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return Settings()

    return Settings(
        default_mode=raw.get("default_mode", "extension"),
        date_format=raw.get("date_format", "%Y-%m"),
        skip_names=list(raw.get("skip_names", DEFAULT_SKIP_NAMES)),
        skip_prefixes=list(raw.get("skip_prefixes", DEFAULT_SKIP_PREFIXES)),
    )


def save_settings(settings: Settings, path: Path | None = None) -> None:
    path = path or SETTINGS_FILE
    path.write_text(
        yaml.dump(settings.to_dict(), sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def update_settings(partial: dict, path: Path | None = None) -> Settings:
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

    updated = Settings(**data)
    save_settings(updated, path)
    return updated
"""Export / import a single config bundle: rules + settings + schedules."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import yaml

import organizer
import scheduler as scheduler_mod
import settings as settings_mod


BUNDLE_VERSION = 1


# ---------- helpers ----------

def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(
        yaml.dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


# ---------- export ----------

def export_bundle() -> dict:
    """Return a JSON-serialisable bundle of all config."""
    return {
        "version": BUNDLE_VERSION,
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rules": _read_yaml(organizer.RULES_FILE),
        "settings": _read_yaml(settings_mod.SETTINGS_FILE),
        "schedules": _read_yaml(scheduler_mod.SCHEDULES_FILE) or {"schedules": []},
    }


# ---------- import ----------

def import_bundle(bundle: dict, strategy: str = "replace") -> dict:
    """Apply a config bundle. strategy: 'replace' or 'merge'."""
    if not isinstance(bundle, dict):
        raise ValueError("Bundle must be a JSON object")
    if strategy not in ("replace", "merge"):
        raise ValueError(f"Invalid strategy: {strategy}")

    applied = {"rules": 0, "settings": False, "schedules": 0}

    rules = bundle.get("rules")
    if isinstance(rules, dict):
        applied["rules"] = _apply_rules(rules, strategy)

    settings = bundle.get("settings")
    if isinstance(settings, dict):
        applied["settings"] = _apply_settings(settings, strategy)

    schedules = bundle.get("schedules")
    if isinstance(schedules, dict):
        applied["schedules"] = _apply_schedules(schedules, strategy)

    return applied


def _apply_rules(incoming: dict, strategy: str) -> int:
    if strategy == "replace":
        _write_yaml(organizer.RULES_FILE, incoming)
        return len(incoming)

    current = _read_yaml(organizer.RULES_FILE)
    for cat, cfg in incoming.items():
        if not isinstance(cfg, dict):
            continue
        exts = set(cfg.get("extensions") or [])
        if cat in current and isinstance(current[cat], dict):
            existing = set(current[cat].get("extensions") or [])
            current[cat]["extensions"] = sorted(existing | exts)
        else:
            current[cat] = {"extensions": sorted(exts)}
    _write_yaml(organizer.RULES_FILE, current)
    return len(incoming)


def _apply_settings(incoming: dict, strategy: str) -> bool:
    # Validate shape before writing
    skip_names = incoming.get("skip_names")
    if skip_names is not None and not isinstance(skip_names, list):
        return False

    skip_prefixes = incoming.get("skip_prefixes")
    if skip_prefixes is not None and not isinstance(skip_prefixes, list):
        return False

    try:
        settings_mod.Settings(
            default_mode=incoming.get("default_mode", "extension"),
            date_format=incoming.get("date_format", "%Y-%m"),
            skip_names=list(skip_names or []),
            skip_prefixes=list(skip_prefixes or []),
        )
    except Exception:
        return False

    if strategy == "replace":
        _write_yaml(settings_mod.SETTINGS_FILE, incoming)
        return True

    current = _read_yaml(settings_mod.SETTINGS_FILE) or {}
    for k, v in incoming.items():
        current[k] = v
    _write_yaml(settings_mod.SETTINGS_FILE, current)
    return True


def _apply_schedules(incoming: dict, strategy: str) -> int:
    new_schedules = incoming.get("schedules") or []
    if not isinstance(new_schedules, list):
        return 0

    if strategy == "replace":
        # Fresh IDs, clear run history
        clean = []
        for s in new_schedules:
            if not isinstance(s, dict):
                continue
            entry = {
                "id": uuid.uuid4().hex[:8],
                "folder": s.get("folder", ""),
                "mode": s.get("mode", "extension"),
                "interval_minutes": int(s.get("interval_minutes", 60)),
                "enabled": bool(s.get("enabled", True)),
                "last_run": None,
                "last_log": None,
                "last_moved": 0,
                "last_error": None,
            }
            if entry["folder"]:
                clean.append(entry)
        _write_yaml(scheduler_mod.SCHEDULES_FILE, {"schedules": clean})
        return len(clean)

    current = _read_yaml(scheduler_mod.SCHEDULES_FILE) or {"schedules": []}
    existing = current.get("schedules") or []
    existing_folders = {s.get("folder") for s in existing}

    added = 0
    for s in new_schedules:
        if not isinstance(s, dict):
            continue
        if s.get("folder") in existing_folders:
            continue
        entry = {
            "id": uuid.uuid4().hex[:8],
            "folder": s.get("folder", ""),
            "mode": s.get("mode", "extension"),
            "interval_minutes": int(s.get("interval_minutes", 60)),
            "enabled": bool(s.get("enabled", True)),
            "last_run": None,
            "last_log": None,
            "last_moved": 0,
            "last_error": None,
        }
        if entry["folder"]:
            existing.append(entry)
            added += 1

    current["schedules"] = existing
    _write_yaml(scheduler_mod.SCHEDULES_FILE, current)
    return added


# ---------- reset ----------

def reset_all() -> dict:
    """Wipe rules / settings / schedules back to defaults."""
    default_rules = {
        "Images": {"extensions": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp", ".svg"]},
        "Documents": {"extensions": [".pdf", ".docx", ".doc", ".txt", ".md", ".xlsx", ".xls", ".pptx", ".csv"]},
        "Archives": {"extensions": [".zip", ".tar", ".gz", ".rar", ".7z", ".bz2"]},
        "Media": {"extensions": [".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".flac", ".m4a"]},
        "Code": {"extensions": [".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".c", ".cpp", ".html", ".css", ".json", ".yaml", ".yml"]},
        "Installers": {"extensions": [".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm"]},
        "Fonts": {"extensions": [".ttf", ".otf", ".woff", ".woff2"]},
    }
    _write_yaml(organizer.RULES_FILE, default_rules)
    settings_mod.save_settings(settings_mod.Settings())
    _write_yaml(scheduler_mod.SCHEDULES_FILE, {"schedules": []})
    return {"ok": True}
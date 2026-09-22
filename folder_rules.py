"""Per-folder rule overrides.

Stored in folder_rules.yaml as:
    folders:
      - path: /abs/path/to/folder
        rules:
          Category: [.ext, .ext]
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from paths import FOLDER_RULES_FILE


def _key(p: str | Path) -> str:
    """Normalised path for comparison (case-insensitive on Windows)."""
    try:
        resolved = Path(p).expanduser().resolve()
    except (OSError, RuntimeError):
        resolved = Path(p).expanduser().absolute()
    return os.path.normcase(str(resolved))


def _normalise_ext(ext: str) -> str:
    ext = str(ext).strip().lower()
    if ext and not ext.startswith("."):
        ext = "." + ext
    return ext


def _load_raw(path: Path | None = None) -> dict:
    path = path or FOLDER_RULES_FILE
    if not path.exists():
        return {"folders": []}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {"folders": []}
    except Exception:
        return {"folders": []}


def _save_raw(data: dict, path: Path | None = None) -> None:
    path = path or FOLDER_RULES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def list_folder_rules() -> list[dict]:
    """Return all folder rule entries, sorted by path."""
    raw = _load_raw()
    folders = [f for f in (raw.get("folders") or []) if isinstance(f, dict)]
    folders.sort(key=lambda f: f.get("path", "").lower())
    return folders


def get_folder_rule(folder_path: str | Path) -> dict | None:
    """Exact-path match. Returns {path, rules} or None."""
    target = _key(folder_path)
    for entry in list_folder_rules():
        if _key(entry.get("path", "")) == target:
            return entry
    return None


def set_folder_rule(folder_path: str | Path, rules: dict) -> dict:
    """Upsert the rule set for a folder. rules = {Category: [ext, ...]}."""
    resolved = str(Path(folder_path).expanduser().resolve())
    clean: dict[str, list[str]] = {}
    for name, exts in (rules or {}).items():
        name = str(name).strip()
        if not name:
            continue
        ext_list = sorted({_normalise_ext(e) for e in (exts or []) if _normalise_ext(e)})
        clean[name] = ext_list

    raw = _load_raw()
    folders = [f for f in (raw.get("folders") or []) if isinstance(f, dict)]
    target = _key(resolved)
    folders = [f for f in folders if _key(f.get("path", "")) != target]
    entry = {"path": resolved, "rules": clean}
    folders.append(entry)
    raw["folders"] = folders
    _save_raw(raw)
    return entry


def remove_folder_rule(folder_path: str | Path) -> None:
    target = _key(folder_path)
    raw = _load_raw()
    folders = [f for f in (raw.get("folders") or []) if isinstance(f, dict)]
    before = len(folders)
    folders = [f for f in folders if _key(f.get("path", "")) != target]
    if len(folders) == before:
        raise KeyError(f"Folder rule not found: {folder_path}")
    raw["folders"] = folders
    _save_raw(raw)


def resolve_rules_for(folder: str | Path, global_rules: list) -> list:
    """
    Return the effective rule list for a folder.

    If the folder has a specific rule set, global categories are used as the
    base and folder rules override categories by name. Otherwise the global
    rules are returned unchanged.
    """
    from organizer import Rule

    entry = get_folder_rule(folder)
    if not entry:
        return global_rules

    merged: dict[str, set[str]] = {r.name: set(r.extensions) for r in global_rules}
    for name, exts in (entry.get("rules") or {}).items():
        merged[name] = set(exts)

    return [Rule(name=name, extensions=exts) for name, exts in merged.items()]


def reset_all(path: Path | None = None) -> None:
    _save_raw({"folders": []}, path)
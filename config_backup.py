"""Timed snapshots of the app configuration.

Backups are stored as JSON files under DATA_DIR/backups/.
Each snapshot is a full config bundle — same shape as /api/config/export.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from config_io import export_bundle, import_bundle
from paths import _DATA_DIR   # reuse the data dir resolver


BACKUP_DIR = _DATA_DIR / "backups"
DEFAULT_KEEP = 30
DEFAULT_INTERVAL_HOURS = 24


def _ensure_dir() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def create_backup(label: str = "") -> dict:
    """
    Write a snapshot to backups/config_YYYYMMDD_HHMMSS.json.
    `label` is optional and appended to the filename.
    Returns metadata about the new backup.
    """
    _ensure_dir()
    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    suffix = f"_{label}" if label else ""
    filename = f"config_{stamp}{suffix}.json"
    path = BACKUP_DIR / filename

    bundle = export_bundle()
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    return {
        "filename": filename,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "size_bytes": path.stat().st_size,
    }


def list_backups() -> list[dict]:
    """Return metadata for every snapshot, newest first."""
    if not BACKUP_DIR.exists():
        return []

    entries: list[dict] = []
    for f in BACKUP_DIR.glob("config_*.json"):
        try:
            stat = f.stat()
            entries.append({
                "filename": f.name,
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "size_bytes": stat.st_size,
            })
        except OSError:
            continue

    entries.sort(key=lambda e: e["created_at"], reverse=True)
    return entries


def read_backup(filename: str) -> dict:
    """Return the parsed bundle. Raises if the file is missing or invalid."""
    # Reject paths that try to escape BACKUP_DIR
    safe = Path(filename).name
    path = BACKUP_DIR / safe
    if not path.exists():
        raise FileNotFoundError(f"Backup not found: {filename}")
    return json.loads(path.read_text(encoding="utf-8"))


def restore_backup(filename: str, strategy: str = "replace") -> dict:
    """Load the snapshot and apply it as a config import."""
    bundle = read_backup(filename)
    return import_bundle(bundle, strategy=strategy)


def delete_backup(filename: str) -> None:
    safe = Path(filename).name
    path = BACKUP_DIR / safe
    if not path.exists():
        raise FileNotFoundError(f"Backup not found: {filename}")
    path.unlink()


def prune_old_backups(keep: int = DEFAULT_KEEP) -> int:
    """Delete all but the newest `keep` snapshots. Returns how many were removed."""
    entries = list_backups()
    if len(entries) <= keep:
        return 0
    removed = 0
    for entry in entries[keep:]:
        try:
            delete_backup(entry["filename"])
            removed += 1
        except OSError:
            pass
    return removed


def should_backup_now(interval_hours: int) -> bool:
    """True if the newest backup is older than interval_hours (or none exists)."""
    entries = list_backups()
    if not entries:
        return True
    newest_time = datetime.strptime(entries[0]["created_at"], "%Y-%m-%d %H:%M:%S")
    return datetime.now() - newest_time >= timedelta(hours=interval_hours)


def run_scheduled_backup() -> dict | None:
    """
    Called by the scheduler tick. Checks the interval, creates a backup
    if due, prunes old ones. Returns the new backup metadata, or None.
    """
    from settings import load_settings

    s = load_settings()
    if not s.backup_enabled:
        return None
    if not should_backup_now(s.backup_interval_hours):
        return None

    meta = create_backup()
    prune_old_backups(keep=s.backup_keep_count)

    # Publish so the UI refreshes
    try:
        import events
        events.publish("backup_created", meta)
    except Exception:
        pass

    return meta
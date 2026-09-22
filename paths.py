"""Resolve config paths.

By default everything lives next to the source files (dev mode).
In Docker, FO_DATA_DIR is set to /app/data, so all writable state
goes there and can be persisted via a volume mount.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


_SOURCE_DIR = Path(__file__).parent
_env_dir = os.environ.get("FO_DATA_DIR")
_DATA_DIR = Path(_env_dir).resolve() if _env_dir else _SOURCE_DIR

RULES_FILE = _DATA_DIR / "rules.yaml"
SETTINGS_FILE = _DATA_DIR / "settings.yaml"
SCHEDULES_FILE = _DATA_DIR / "schedules.yaml"
FOLDER_RULES_FILE = _DATA_DIR / "folder_rules.yaml"
LOG_DIR = _DATA_DIR / "logs"

if _env_dir:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _source_rules = _SOURCE_DIR / "rules.yaml"
    if not RULES_FILE.exists() and _source_rules.exists():
        try:
            shutil.copy(_source_rules, RULES_FILE)
        except OSError:
            pass
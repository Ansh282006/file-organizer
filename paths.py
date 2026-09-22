"""Resolve config paths.

Handles three environments:
  1. Dev mode       — source files, config lives next to source
  2. Docker         — FO_DATA_DIR set, config lives under /app/data
  3. Frozen (PyInstaller) — sys.frozen set, config lives next to the .exe
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _runtime_dir() -> Path:
    """Where the app is actually running from."""
    if getattr(sys, "frozen", False):
        # PyInstaller: use the folder containing the .exe
        return Path(sys.executable).parent
    return Path(__file__).parent


def _bundle_dir() -> Path:
    """Where bundled data (static/, rules.yaml seed) lives."""
    if getattr(sys, "frozen", False):
        # PyInstaller extracts to sys._MEIPASS
        return Path(getattr(sys, "_MEIPASS", _runtime_dir()))
    return Path(__file__).parent


RUNTIME_DIR = _runtime_dir()
BUNDLE_DIR = _bundle_dir()

_env_dir = os.environ.get("FO_DATA_DIR")
if _env_dir:
    _DATA_DIR = Path(_env_dir).resolve()
elif getattr(sys, "frozen", False):
    # Frozen: store config next to the executable
    _DATA_DIR = RUNTIME_DIR / "data"
else:
    _DATA_DIR = RUNTIME_DIR

RULES_FILE = _DATA_DIR / "rules.yaml"
SETTINGS_FILE = _DATA_DIR / "settings.yaml"
SCHEDULES_FILE = _DATA_DIR / "schedules.yaml"
FOLDER_RULES_FILE = _DATA_DIR / "folder_rules.yaml"
LOG_DIR = _DATA_DIR / "logs"
STATIC_DIR = BUNDLE_DIR / "static"

# Ensure data dir exists
_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Seed rules.yaml on first run
_source_rules = BUNDLE_DIR / "rules.yaml"
if not RULES_FILE.exists() and _source_rules.exists():
    try:
        shutil.copy(_source_rules, RULES_FILE)
    except OSError:
        pass
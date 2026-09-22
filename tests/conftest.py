"""Shared pytest fixtures."""

import os
import tempfile
from pathlib import Path

# IMPORTANT: Set FO_DATA_DIR BEFORE any app modules are imported.
# All config files (rules.yaml, settings.yaml, etc.) will live under this
# dir for the duration of the test session — no real config is touched.
_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="file-organizer-test-"))
os.environ.setdefault("FO_DATA_DIR", str(_TEST_DATA_DIR))

import pytest  # noqa: E402

import folder_rules  # noqa: E402
import organizer  # noqa: E402
import scheduler as scheduler_mod  # noqa: E402
import settings as settings_mod  # noqa: E402


RULES_YAML = """\
Images:
  extensions: [.jpg, .png]

Documents:
  extensions: [.pdf, .txt]

Code:
  extensions: [.py, .js]
"""


# ============================================================
# Unit-test fixtures (per-test isolation)
# ============================================================

@pytest.fixture
def rules_file(tmp_path, monkeypatch):
    """A temporary rules.yaml that tests can point organizer at."""
    rf = tmp_path / "rules.yaml"
    rf.write_text(RULES_YAML, encoding="utf-8")
    monkeypatch.setattr(organizer, "RULES_FILE", rf)
    return rf


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """A temporary logs/ folder so tests never touch the real one."""
    ld = tmp_path / "logs"
    ld.mkdir()
    monkeypatch.setattr(organizer, "LOG_DIR", ld)
    return ld


@pytest.fixture
def workdir(tmp_path):
    """A clean folder to organize."""
    d = tmp_path / "workdir"
    d.mkdir()
    return d


# ============================================================
# End-to-end test fixtures (session-scoped data dir)
# ============================================================

def _reset_test_config() -> None:
    """Wipe the session data dir and seed it with default rules."""
    for name in ("rules.yaml", "settings.yaml", "schedules.yaml", "folder_rules.yaml"):
        p = _TEST_DATA_DIR / name
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass

    log_dir = _TEST_DATA_DIR / "logs"
    if log_dir.exists():
        for f in log_dir.glob("*.json"):
            try:
                f.unlink()
            except OSError:
                pass

    # Seed default rules.yaml from the repo
    src = Path(__file__).parent.parent / "rules.yaml"
    if src.exists():
        (_TEST_DATA_DIR / "rules.yaml").write_text(src.read_text(encoding="utf-8"))


@pytest.fixture
def app_client():
    """
    FastAPI TestClient connected to the real app, with isolated config.

    Use it exactly like `requests`:
        r = app_client.get("/api/health")
        r = app_client.post("/api/organize", json={...})
    """
    _reset_test_config()

    from fastapi.testclient import TestClient
    import app as app_module

    with TestClient(app_module.app) as client:
        yield client
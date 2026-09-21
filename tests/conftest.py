"""Shared pytest fixtures."""

import pytest

import organizer


RULES_YAML = """\
Images:
  extensions: [.jpg, .png]

Documents:
  extensions: [.pdf, .txt]

Code:
  extensions: [.py, .js]
"""


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
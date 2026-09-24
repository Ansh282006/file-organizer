"""Tests for config backups."""

import json
import time
from pathlib import Path

import pytest

import config_backup


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    d = tmp_path / "backups"
    d.mkdir()
    monkeypatch.setattr(config_backup, "BACKUP_DIR", d)
    return d


@pytest.fixture
def fake_export(monkeypatch):
    """Replace export_bundle with a stub so tests don't touch real config."""
    def _stub():
        return {
            "version": 1,
            "exported_at": "2026-01-01 00:00:00",
            "rules": {"Images": {"extensions": [".jpg"]}},
            "settings": {},
            "schedules": {"schedules": []},
            "folder_rules": {"folders": []},
        }
    import config_io
    monkeypatch.setattr(config_backup, "export_bundle", _stub)


def test_create_backup(backup_dir, fake_export):
    meta = config_backup.create_backup()
    assert meta["filename"].startswith("config_")
    assert meta["filename"].endswith(".json")
    assert meta["size_bytes"] > 0
    assert (backup_dir / meta["filename"]).exists()


def test_create_backup_with_label(backup_dir, fake_export):
    meta = config_backup.create_backup(label="before-change")
    assert "before-change" in meta["filename"]


def test_list_backups(backup_dir, fake_export):
    config_backup.create_backup()
    time.sleep(1.1)  # so timestamps differ
    config_backup.create_backup()
    entries = config_backup.list_backups()
    assert len(entries) == 2
    # Newest first
    assert entries[0]["created_at"] >= entries[1]["created_at"]


def test_list_empty(backup_dir):
    assert config_backup.list_backups() == []


def test_read_backup(backup_dir, fake_export):
    meta = config_backup.create_backup()
    bundle = config_backup.read_backup(meta["filename"])
    assert bundle["version"] == 1
    assert "rules" in bundle


def test_read_missing_raises(backup_dir):
    with pytest.raises(FileNotFoundError):
        config_backup.read_backup("nope.json")


def test_delete_backup(backup_dir, fake_export):
    meta = config_backup.create_backup()
    config_backup.delete_backup(meta["filename"])
    assert config_backup.list_backups() == []


def test_delete_missing_raises(backup_dir):
    with pytest.raises(FileNotFoundError):
        config_backup.delete_backup("nope.json")


def test_prune_keeps_newest(backup_dir, fake_export):
    for _ in range(5):
        config_backup.create_backup()
        time.sleep(1.05)
    removed = config_backup.prune_old_backups(keep=2)
    assert removed == 3
    assert len(config_backup.list_backups()) == 2


def test_prune_noop_when_under_limit(backup_dir, fake_export):
    config_backup.create_backup()
    assert config_backup.prune_old_backups(keep=5) == 0


def test_should_backup_now_when_empty(backup_dir):
    assert config_backup.should_backup_now(24) is True


def test_should_backup_now_after_recent(backup_dir, fake_export):
    config_backup.create_backup()
    assert config_backup.should_backup_now(24) is False


def test_read_backup_rejects_path_traversal(backup_dir):
    # Try to escape the backups folder
    with pytest.raises(FileNotFoundError):
        config_backup.read_backup("../../etc/passwd")


def test_filename_sanitisation(backup_dir, fake_export):
    """A crafted filename should be reduced to its basename."""
    meta = config_backup.create_backup()
    # Try to read via a path-traversal variant
    bundle = config_backup.read_backup(f"./{meta['filename']}")
    assert bundle["version"] == 1
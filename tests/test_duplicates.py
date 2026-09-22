"""Tests for duplicate detection and quarantine."""

import time

import pytest

import organizer
from duplicates import find_duplicates, plan_quarantine


def touch(folder, name, content="x"):
    p = folder / name
    p.write_text(content, encoding="utf-8")
    return p


def test_no_duplicates(workdir):
    touch(workdir, "a.txt", "hello")
    touch(workdir, "b.txt", "world")
    result = find_duplicates(workdir)
    assert result["total_groups"] == 0
    assert result["total_files"] == 2


def test_basic_duplicate(workdir):
    touch(workdir, "a.txt", "same")
    touch(workdir, "b.txt", "same")
    result = find_duplicates(workdir)
    assert result["total_groups"] == 1
    assert len(result["groups"][0]["files"]) == 2
    assert result["wasted_bytes"] == 4


def test_three_way_duplicate(workdir):
    touch(workdir, "a.txt", "same")
    touch(workdir, "b.txt", "same")
    touch(workdir, "c.txt", "same")
    result = find_duplicates(workdir)
    assert result["total_groups"] == 1
    assert len(result["groups"][0]["files"]) == 3
    assert result["wasted_bytes"] == 8  # 2 extra copies × 4 bytes


def test_same_size_different_content(workdir):
    touch(workdir, "a.txt", "abcd")
    touch(workdir, "b.txt", "wxyz")  # same size, different content
    result = find_duplicates(workdir)
    assert result["total_groups"] == 0


def test_empty_files_ignored(workdir):
    touch(workdir, "a.txt", "")
    touch(workdir, "b.txt", "")
    result = find_duplicates(workdir)
    assert result["total_groups"] == 0


def test_subfolders_ignored(workdir):
    (workdir / "sub").mkdir()
    touch(workdir / "sub", "a.txt", "same")
    touch(workdir, "b.txt", "same")
    result = find_duplicates(workdir)
    assert result["total_groups"] == 0  # only top-level considered


def test_skip_names_respected(workdir):
    touch(workdir, "a.txt", "same")
    touch(workdir, ".DS_Store", "same")
    result = find_duplicates(workdir, skip_names={".DS_Store"})
    assert result["total_groups"] == 0


def test_nonexistent_folder_raises(tmp_path):
    with pytest.raises(NotADirectoryError):
        find_duplicates(tmp_path / "nope")


def test_groups_sorted_by_wasted_bytes(workdir):
    # Group 1: 2 copies of 4-byte file = 4 bytes wasted
    touch(workdir, "a1.txt", "aaaa")
    touch(workdir, "a2.txt", "aaaa")
    # Group 2: 3 copies of 10-byte file = 20 bytes wasted
    touch(workdir, "b1.txt", "0123456789")
    touch(workdir, "b2.txt", "0123456789")
    touch(workdir, "b3.txt", "0123456789")

    result = find_duplicates(workdir)
    assert result["total_groups"] == 2
    # Bigger waste first
    assert result["groups"][0]["wasted_bytes"] == 20


def test_quarantine_plan_keeps_newest(workdir, monkeypatch, log_dir):
    """Newest file in a group stays; older ones go to _duplicates/."""
    # Create older file first
    old = touch(workdir, "old.txt", "same")
    time.sleep(0.05)
    new = touch(workdir, "new.txt", "same")
    # Touch the new one to ensure its mtime is definitely newer
    new.touch()

    result = find_duplicates(workdir)
    assert result["total_groups"] == 1
    # First file in group should be newest (new.txt)
    assert result["groups"][0]["files"][0]["name"] == "new.txt"

    plan = plan_quarantine(workdir, result["groups"])
    assert plan.total == 1
    assert plan.items[0].source.name == "old.txt"


def test_quarantine_execute_and_undo(workdir, monkeypatch, log_dir):
    """Full cycle: duplicate → quarantine → undo."""
    from organizer import execute, undo

    touch(workdir, "a.txt", "same")
    time.sleep(0.05)
    touch(workdir, "b.txt", "same")

    result = find_duplicates(workdir)
    plan = plan_quarantine(workdir, result["groups"])
    log_path = execute(plan)

    # One file should have moved to _duplicates/
    assert (workdir / "_duplicates").is_dir()
    assert len(list((workdir / "_duplicates").iterdir())) == 1

    # Undo restores it
    undo_result = undo(log_path)
    assert undo_result["restored"] == 1
    assert not (workdir / "_duplicates").exists()
    assert (workdir / "a.txt").exists()
    assert (workdir / "b.txt").exists()
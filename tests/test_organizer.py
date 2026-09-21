"""Tests for organizer.py — scan, execute, undo, rules, date mode."""

import json
import os
import time

import pytest

import organizer
from organizer import (
    add_category,
    add_extension,
    execute,
    latest_undoable_log,
    list_logs,
    load_rules,
    remove_category,
    remove_extension,
    scan,
    undo,
)


def touch(folder, name, content="x"):
    p = folder / name
    p.write_text(content, encoding="utf-8")
    return p


def set_mtime(path, year, month, day=15, hour=12):
    """Set a file's mtime to a specific date."""
    t = time.mktime((year, month, day, hour, 0, 0, 0, 0, 0))
    os.utime(path, (t, t))


# ============================================================
# scan — extension mode
# ============================================================

def test_scan_basic(workdir, rules_file):
    touch(workdir, "a.jpg")
    touch(workdir, "b.pdf")
    touch(workdir, "c.py")
    plan = scan(workdir, load_rules())
    assert plan.total == 3
    cats = {it.category for it in plan.items}
    assert cats == {"Images", "Documents", "Code"}


def test_scan_unknown_goes_to_misc(workdir, rules_file):
    touch(workdir, "mystery.xyz")
    plan = scan(workdir, load_rules())
    assert plan.items[0].category == "Misc"


def test_scan_skips_hidden(workdir, rules_file):
    touch(workdir, ".secret")
    touch(workdir, ".DS_Store")
    touch(workdir, "visible.jpg")
    plan = scan(workdir, load_rules())
    assert plan.total == 1
    assert len(plan.skipped) == 2


def test_scan_skips_already_sorted(workdir, rules_file):
    (workdir / "Images").mkdir()
    touch(workdir / "Images", "old.jpg")
    touch(workdir, "new.jpg")
    plan = scan(workdir, load_rules())
    assert plan.total == 1


def test_scan_empty_folder(workdir, rules_file):
    assert scan(workdir, load_rules()).total == 0


def test_scan_ignores_subfolders(workdir, rules_file):
    (workdir / "subdir").mkdir()
    touch(workdir / "subdir", "a.jpg")
    touch(workdir, "b.jpg")
    plan = scan(workdir, load_rules())
    assert plan.total == 1


def test_scan_nonexistent_raises(tmp_path, rules_file):
    with pytest.raises(NotADirectoryError):
        scan(tmp_path / "nope", load_rules())


def test_scan_case_insensitive_extension(workdir, rules_file):
    touch(workdir, "PHOTO.JPG")
    plan = scan(workdir, load_rules())
    assert plan.items[0].category == "Images"


# ============================================================
# scan — date mode
# ============================================================

def test_scan_date_mode(workdir, rules_file):
    p = touch(workdir, "a.jpg")
    set_mtime(p, 2026, 9)
    plan = scan(workdir, mode="date")
    assert plan.total == 1
    assert plan.items[0].category == "2026-09"


def test_scan_date_mode_groups_by_month(workdir, rules_file):
    p1 = touch(workdir, "sep.jpg")
    p2 = touch(workdir, "aug.jpg")
    set_mtime(p1, 2026, 9)
    set_mtime(p2, 2026, 8)
    plan = scan(workdir, mode="date")
    cats = {it.category for it in plan.items}
    assert cats == {"2026-09", "2026-08"}


def test_scan_date_mode_ignores_extension(workdir, rules_file):
    p1 = touch(workdir, "a.jpg")
    p2 = touch(workdir, "b.pdf")
    set_mtime(p1, 2026, 9)
    set_mtime(p2, 2026, 9)
    plan = scan(workdir, mode="date")
    # Both go to 2026-09, not Images/Documents
    cats = {it.category for it in plan.items}
    assert cats == {"2026-09"}


def test_scan_date_mode_skips_already_sorted(workdir, rules_file):
    (workdir / "2026-09").mkdir()
    p = touch(workdir / "2026-09", "old.jpg")
    set_mtime(p, 2026, 9)
    p2 = touch(workdir, "new.jpg")
    set_mtime(p2, 2026, 9)
    plan = scan(workdir, mode="date")
    assert plan.total == 1
    assert plan.items[0].source.name == "new.jpg"


def test_scan_invalid_mode_raises(workdir, rules_file):
    with pytest.raises(ValueError):
        scan(workdir, mode="banana")


# ============================================================
# collision
# ============================================================

def test_collision_with_existing(workdir, rules_file):
    (workdir / "Images").mkdir()
    touch(workdir / "Images", "photo.jpg")
    touch(workdir, "photo.jpg")
    plan = scan(workdir, load_rules())
    assert plan.items[0].renamed is True
    assert plan.items[0].destination.name == "photo_1.jpg"


def test_double_collision(workdir, rules_file):
    (workdir / "Images").mkdir()
    touch(workdir / "Images", "photo.jpg")
    touch(workdir / "Images", "photo_1.jpg")
    touch(workdir, "photo.jpg")
    plan = scan(workdir, load_rules())
    assert plan.items[0].destination.name == "photo_2.jpg"


# ============================================================
# execute
# ============================================================

def test_execute_moves_files(workdir, rules_file, log_dir):
    touch(workdir, "a.jpg")
    touch(workdir, "b.pdf")
    log_path = execute(scan(workdir, load_rules()))
    assert (workdir / "Images" / "a.jpg").exists()
    assert (workdir / "Documents" / "b.pdf").exists()
    assert log_path.exists()


def test_execute_logs_mode(workdir, rules_file, log_dir):
    p = touch(workdir, "a.jpg")
    set_mtime(p, 2026, 9)
    log_path = execute(scan(workdir, mode="date"))
    data = json.loads(log_path.read_text())
    assert data["mode"] == "date"


def test_execute_empty_plan(workdir, rules_file, log_dir):
    log_path = execute(scan(workdir, load_rules()))
    assert json.loads(log_path.read_text())["total"] == 0


# ============================================================
# undo
# ============================================================

def test_undo_restores_files(workdir, rules_file, log_dir):
    touch(workdir, "a.jpg")
    touch(workdir, "b.pdf")
    log_path = execute(scan(workdir, load_rules()))
    result = undo(log_path)
    assert result["restored"] == 2
    assert (workdir / "a.jpg").exists()
    assert (workdir / "b.pdf").exists()


def test_undo_date_mode(workdir, rules_file, log_dir):
    p = touch(workdir, "a.jpg")
    set_mtime(p, 2026, 9)
    log_path = execute(scan(workdir, mode="date"))
    undo(log_path)
    assert (workdir / "a.jpg").exists()
    assert not (workdir / "2026-09").exists()


def test_undo_twice_fails(workdir, rules_file, log_dir):
    touch(workdir, "a.jpg")
    log_path = execute(scan(workdir, load_rules()))
    undo(log_path)
    with pytest.raises(ValueError):
        undo(log_path)


def test_undo_missing_file_reports_error(workdir, rules_file, log_dir):
    touch(workdir, "a.jpg")
    touch(workdir, "b.jpg")
    log_path = execute(scan(workdir, load_rules()))
    (workdir / "Images" / "a.jpg").unlink()
    result = undo(log_path)
    assert result["restored"] == 1
    assert len(result["errors"]) == 1


def test_undo_nonexistent_log_raises(log_dir):
    with pytest.raises(FileNotFoundError):
        undo(log_dir / "nope.json")


# ============================================================
# logs
# ============================================================

def test_list_logs_empty(log_dir):
    assert list_logs() == []


def test_list_logs_after_execute(workdir, rules_file, log_dir):
    touch(workdir, "a.jpg")
    log_path = execute(scan(workdir, load_rules()))
    logs = list_logs()
    assert len(logs) == 1
    assert logs[0]["file"] == log_path.name


def test_latest_undoable_skips_done(workdir, rules_file, log_dir):
    touch(workdir, "a.jpg")
    p = execute(scan(workdir, load_rules()))
    assert latest_undoable_log() is not None
    undo(p)
    assert latest_undoable_log() is None


# ============================================================
# rules editing
# ============================================================

def test_add_extension(rules_file):
    add_extension("Images", ".heif")
    images = next(r for r in load_rules() if r.name == "Images")
    assert ".heif" in images.extensions


def test_add_extension_normalises_dot(rules_file):
    add_extension("Images", "heif")
    images = next(r for r in load_rules() if r.name == "Images")
    assert ".heif" in images.extensions


def test_add_extension_unknown_category(rules_file):
    with pytest.raises(KeyError):
        add_extension("Nope", ".jpg")


def test_add_extension_empty(rules_file):
    with pytest.raises(ValueError):
        add_extension("Images", "")


def test_remove_extension(rules_file):
    remove_extension("Images", ".jpg")
    images = next(r for r in load_rules() if r.name == "Images")
    assert ".jpg" not in images.extensions


def test_add_category(rules_file):
    add_category("Videos", [".mp4", ".mkv"])
    names = [r.name for r in load_rules()]
    assert "Videos" in names


def test_add_duplicate_category_fails(rules_file):
    with pytest.raises(ValueError):
        add_category("Images")


def test_add_empty_category_fails(rules_file):
    with pytest.raises(ValueError):
        add_category("   ")


def test_remove_category(rules_file):
    remove_category("Images")
    names = [r.name for r in load_rules()]
    assert "Images" not in names


def test_remove_unknown_category(rules_file):
    with pytest.raises(KeyError):
        remove_category("Nope")
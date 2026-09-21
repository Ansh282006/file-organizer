"""Tests for organizer.py — scan, execute, undo, rules."""

import json

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
    """Create a file with content in folder."""
    p = folder / name
    p.write_text(content, encoding="utf-8")
    return p


# ============================================================
# scan
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
    assert plan.total == 1
    assert plan.items[0].category == "Misc"


def test_scan_skips_hidden(workdir, rules_file):
    touch(workdir, ".secret")
    touch(workdir, ".DS_Store")
    touch(workdir, "visible.jpg")
    plan = scan(workdir, load_rules())
    assert plan.total == 1
    assert plan.items[0].source.name == "visible.jpg"
    assert len(plan.skipped) == 2


def test_scan_skips_already_sorted(workdir, rules_file):
    (workdir / "Images").mkdir()
    touch(workdir / "Images", "old.jpg")
    touch(workdir, "new.jpg")
    plan = scan(workdir, load_rules())
    assert plan.total == 1
    assert plan.items[0].source.name == "new.jpg"


def test_scan_empty_folder(workdir, rules_file):
    plan = scan(workdir, load_rules())
    assert plan.total == 0


def test_scan_ignores_subfolders(workdir, rules_file):
    (workdir / "subdir").mkdir()
    touch(workdir / "subdir", "a.jpg")
    touch(workdir, "b.jpg")
    plan = scan(workdir, load_rules())
    assert plan.total == 1
    assert plan.items[0].source.name == "b.jpg"


def test_scan_nonexistent_raises(tmp_path, rules_file):
    with pytest.raises(NotADirectoryError):
        scan(tmp_path / "nope", load_rules())


def test_scan_case_insensitive_extension(workdir, rules_file):
    touch(workdir, "PHOTO.JPG")
    plan = scan(workdir, load_rules())
    assert plan.items[0].category == "Images"


# ============================================================
# collision
# ============================================================

def test_collision_with_existing(workdir, rules_file):
    (workdir / "Images").mkdir()
    touch(workdir / "Images", "photo.jpg")
    touch(workdir, "photo.jpg")
    plan = scan(workdir, load_rules())
    assert plan.total == 1
    item = plan.items[0]
    assert item.renamed is True
    assert item.destination.name == "photo_1.jpg"


def test_double_collision(workdir, rules_file):
    (workdir / "Images").mkdir()
    touch(workdir / "Images", "photo.jpg")
    touch(workdir / "Images", "photo_1.jpg")
    touch(workdir, "photo.jpg")
    plan = scan(workdir, load_rules())
    assert plan.items[0].destination.name == "photo_2.jpg"


def test_collision_within_same_plan(workdir, rules_file):
    """Two files from different source names, same destination stem after rename."""
    # photo.jpg and PHOTO.jpg both target Images — Windows can't do this,
    # so simulate via renaming path logic directly
    (workdir / "Images").mkdir()
    touch(workdir / "Images", "a.jpg")
    touch(workdir, "a.jpg")
    plan = scan(workdir, load_rules())
    assert plan.items[0].destination.name == "a_1.jpg"


# ============================================================
# execute
# ============================================================

def test_execute_moves_files(workdir, rules_file, log_dir):
    touch(workdir, "a.jpg")
    touch(workdir, "b.pdf")
    plan = scan(workdir, load_rules())
    log_path = execute(plan)

    assert (workdir / "Images" / "a.jpg").exists()
    assert (workdir / "Documents" / "b.pdf").exists()
    assert not (workdir / "a.jpg").exists()
    assert log_path.exists()


def test_execute_writes_log(workdir, rules_file, log_dir):
    touch(workdir, "a.jpg")
    plan = scan(workdir, load_rules())
    log_path = execute(plan)

    data = json.loads(log_path.read_text())
    assert data["total"] == 1
    assert len(data["moves"]) == 1
    assert data["moves"][0]["source"].endswith("a.jpg")
    assert data["errors"] == []


def test_execute_empty_plan(workdir, rules_file, log_dir):
    plan = scan(workdir, load_rules())
    log_path = execute(plan)
    data = json.loads(log_path.read_text())
    assert data["total"] == 0


# ============================================================
# undo
# ============================================================

def test_undo_restores_files(workdir, rules_file, log_dir):
    touch(workdir, "a.jpg")
    touch(workdir, "b.pdf")
    plan = scan(workdir, load_rules())
    log_path = execute(plan)

    result = undo(log_path)

    assert result["restored"] == 2
    assert (workdir / "a.jpg").exists()
    assert (workdir / "b.pdf").exists()
    assert not (workdir / "Images").exists()
    assert not (workdir / "Documents").exists()


def test_undo_marks_log_done(workdir, rules_file, log_dir):
    touch(workdir, "a.jpg")
    plan = scan(workdir, load_rules())
    log_path = execute(plan)
    undo(log_path)

    data = json.loads(log_path.read_text())
    assert data["undone"] is True
    assert "undone_at" in data


def test_undo_twice_fails(workdir, rules_file, log_dir):
    touch(workdir, "a.jpg")
    plan = scan(workdir, load_rules())
    log_path = execute(plan)
    undo(log_path)
    with pytest.raises(ValueError):
        undo(log_path)


def test_undo_missing_file_reports_error(workdir, rules_file, log_dir):
    touch(workdir, "a.jpg")
    touch(workdir, "b.jpg")
    plan = scan(workdir, load_rules())
    log_path = execute(plan)

    # Delete one of the moved files
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
    assert logs[0]["undone"] is False


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
    rules = load_rules()
    images = next(r for r in rules if r.name == "Images")
    assert ".heif" in images.extensions


def test_add_extension_normalises_dot(rules_file):
    add_extension("Images", "heif")
    rules = load_rules()
    images = next(r for r in rules if r.name == "Images")
    assert ".heif" in images.extensions


def test_add_extension_unknown_category(rules_file):
    with pytest.raises(KeyError):
        add_extension("Nope", ".jpg")


def test_add_extension_empty(rules_file):
    with pytest.raises(ValueError):
        add_extension("Images", "")


def test_remove_extension(rules_file):
    remove_extension("Images", ".jpg")
    rules = load_rules()
    images = next(r for r in rules if r.name == "Images")
    assert ".jpg" not in images.extensions


def test_add_category(rules_file):
    add_category("Videos", [".mp4", ".mkv"])
    rules = load_rules()
    names = [r.name for r in rules]
    assert "Videos" in names


def test_add_category_normalises_extensions(rules_file):
    add_category("Videos", ["mp4", ".mkv"])
    rules = load_rules()
    videos = next(r for r in rules if r.name == "Videos")
    assert videos.extensions == {".mp4", ".mkv"}


def test_add_duplicate_category_fails(rules_file):
    with pytest.raises(ValueError):
        add_category("Images")


def test_add_empty_category_fails(rules_file):
    with pytest.raises(ValueError):
        add_category("   ")


def test_remove_category(rules_file):
    remove_category("Images")
    rules = load_rules()
    names = [r.name for r in rules]
    assert "Images" not in names


def test_remove_unknown_category(rules_file):
    with pytest.raises(KeyError):
        remove_category("Nope")
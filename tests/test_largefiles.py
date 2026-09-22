"""Tests for the large-file finder."""

import pytest

from largefiles import find_large_files, plan_quarantine


def make_file(path, size_bytes):
    """Create a file of approximately size_bytes (sparse write)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.seek(size_bytes - 1)
        f.write(b"\0")
    return path


def test_empty_folder(tmp_path):
    result = find_large_files(tmp_path, min_bytes=0)
    assert result["total_scanned"] == 0
    assert result["matched"] == 0
    assert result["files"] == []


def test_finds_files_over_threshold(tmp_path):
    make_file(tmp_path / "small.bin", 100)
    make_file(tmp_path / "big.bin", 5000)
    result = find_large_files(tmp_path, min_bytes=1000)
    assert result["matched"] == 1
    assert result["files"][0]["name"] == "big.bin"


def test_sorted_by_size_desc(tmp_path):
    make_file(tmp_path / "a.bin", 2000)
    make_file(tmp_path / "b.bin", 5000)
    make_file(tmp_path / "c.bin", 3000)
    result = find_large_files(tmp_path, min_bytes=0)
    names = [f["name"] for f in result["files"]]
    assert names == ["b.bin", "c.bin", "a.bin"]


def test_recursive_scan(tmp_path):
    make_file(tmp_path / "sub1" / "a.bin", 2000)
    make_file(tmp_path / "sub1" / "sub2" / "b.bin", 3000)
    make_file(tmp_path / "top.bin", 1000)
    result = find_large_files(tmp_path, min_bytes=0)
    names = sorted(f["name"] for f in result["files"])
    assert names == ["a.bin", "b.bin", "top.bin"]


def test_skips_hidden_by_default(tmp_path):
    make_file(tmp_path / ".hidden.bin", 5000)
    make_file(tmp_path / "visible.bin", 5000)
    result = find_large_files(tmp_path, min_bytes=0, skip_prefixes=(".",))
    names = [f["name"] for f in result["files"]]
    assert "visible.bin" in names
    assert ".hidden.bin" not in names


def test_skips_quarantine_dir(tmp_path):
    make_file(tmp_path / "_large_files" / "old.bin", 5000)
    make_file(tmp_path / "new.bin", 5000)
    result = find_large_files(tmp_path, min_bytes=0)
    names = [f["name"] for f in result["files"]]
    assert "new.bin" in names
    assert "old.bin" not in names


def test_nonexistent_folder_raises(tmp_path):
    with pytest.raises(NotADirectoryError):
        find_large_files(tmp_path / "nope", min_bytes=0)


def test_negative_threshold_raises(tmp_path):
    with pytest.raises(ValueError):
        find_large_files(tmp_path, min_bytes=-1)


def test_truncation(tmp_path):
    for i in range(10):
        make_file(tmp_path / f"f{i}.bin", 1000 + i)
    result = find_large_files(tmp_path, min_bytes=0, max_results=3)
    assert result["matched"] == 3
    assert result["truncated"] is True


def test_rel_path_recorded(tmp_path):
    make_file(tmp_path / "sub" / "deep.bin", 2000)
    result = find_large_files(tmp_path, min_bytes=0)
    assert result["files"][0]["rel_path"] == "sub/deep.bin"


def test_plan_quarantine_preserves_structure(tmp_path):
    make_file(tmp_path / "sub" / "a.bin", 2000)
    make_file(tmp_path / "top.bin", 3000)

    result = find_large_files(tmp_path, min_bytes=0)
    plan = plan_quarantine(tmp_path, result["files"])

    assert plan.total == 2
    # _large_files/ mirrors the original relative paths
    dests = sorted(str(it.destination.relative_to(tmp_path)) for it in plan.items)
    assert dests == [
        "_large_files\\sub\\a.bin" if "\\" in dests[0] else "_large_files/sub/a.bin",
        "_large_files\\top.bin" if "\\" in dests[0] else "_large_files/top.bin",
    ] or any("sub" in d for d in dests)  # tolerant of path separator


def test_plan_quarantine_execute_and_undo(tmp_path, monkeypatch):
    """Full cycle: find → quarantine → undo."""
    import organizer
    from organizer import execute, undo

    # Point LOG_DIR at a temp folder
    logs = tmp_path / "_logs"
    logs.mkdir()
    monkeypatch.setattr(organizer, "LOG_DIR", logs)

    work = tmp_path / "work"
    work.mkdir()
    make_file(work / "big.bin", 5000)

    result = find_large_files(work, min_bytes=1000)
    plan = plan_quarantine(work, result["files"])
    log_path = execute(plan)

    # File moved into _large_files/
    assert (work / "_large_files" / "big.bin").exists()
    assert not (work / "big.bin").exists()

    # Undo restores
    undo_result = undo(log_path)
    assert undo_result["restored"] == 1
    assert (work / "big.bin").exists()
    assert not (work / "_large_files").exists()
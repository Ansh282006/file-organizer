"""Tests for the scheduler."""

import time
from pathlib import Path

import pytest

import scheduler as sch


@pytest.fixture
def schedules_file(tmp_path, monkeypatch):
    p = tmp_path / "schedules.yaml"
    monkeypatch.setattr(sch, "SCHEDULES_FILE", p)
    return p


@pytest.fixture
def workdir(tmp_path):
    d = tmp_path / "work"
    d.mkdir()
    return d


def touch(folder, name, content="x"):
    p = folder / name
    p.write_text(content, encoding="utf-8")
    return p


def test_list_empty(schedules_file):
    assert sch.list_schedules() == []


def test_add_and_list(schedules_file, workdir):
    sch.add_schedule(str(workdir), mode="extension", interval_minutes=30)
    schedules = sch.list_schedules()
    assert len(schedules) == 1
    assert schedules[0]["folder"] == str(workdir.resolve())
    assert schedules[0]["interval_minutes"] == 30
    assert schedules[0]["enabled"] is True


def test_add_invalid_folder(schedules_file, tmp_path):
    with pytest.raises(NotADirectoryError):
        sch.add_schedule(str(tmp_path / "nope"))


def test_add_invalid_mode(schedules_file, workdir):
    with pytest.raises(ValueError):
        sch.add_schedule(str(workdir), mode="banana")


def test_add_invalid_interval(schedules_file, workdir):
    with pytest.raises(ValueError):
        sch.add_schedule(str(workdir), interval_minutes=0)


def test_update_enabled(schedules_file, workdir):
    entry = sch.add_schedule(str(workdir))
    sch.update_schedule(entry["id"], {"enabled": False})
    s = sch.list_schedules()[0]
    assert s["enabled"] is False


def test_update_interval(schedules_file, workdir):
    entry = sch.add_schedule(str(workdir), interval_minutes=60)
    sch.update_schedule(entry["id"], {"interval_minutes": 15})
    s = sch.list_schedules()[0]
    assert s["interval_minutes"] == 15


def test_remove(schedules_file, workdir):
    entry = sch.add_schedule(str(workdir))
    sch.remove_schedule(entry["id"])
    assert sch.list_schedules() == []


def test_remove_unknown(schedules_file):
    with pytest.raises(KeyError):
        sch.remove_schedule("nope")


def test_run_one_moves_files(schedules_file, workdir, monkeypatch, tmp_path):
    """Force a schedule to run and check it organized the folder."""
    # Point LOG_DIR at a temp folder so the run doesn't touch real logs
    import organizer
    monkeypatch.setattr(organizer, "LOG_DIR", tmp_path / "logs")
    (tmp_path / "logs").mkdir()

    touch(workdir, "a.txt")
    touch(workdir, "b.jpg")

    entry = sch.add_schedule(str(workdir), mode="extension")
    result = sch.run_schedule_now(entry["id"])

    assert result["last_moved"] == 2
    assert result["last_error"] is None
    assert result["last_log"] is not None
    assert (workdir / "Documents" / "a.txt").exists()
    assert (workdir / "Images" / "b.jpg").exists()


def test_run_one_nothing_to_do(schedules_file, workdir, monkeypatch, tmp_path):
    import organizer
    monkeypatch.setattr(organizer, "LOG_DIR", tmp_path / "logs")
    (tmp_path / "logs").mkdir()

    entry = sch.add_schedule(str(workdir))
    result = sch.run_schedule_now(entry["id"])

    assert result["last_moved"] == 0
    assert result["last_log"] is None
    assert result["last_error"] is None


def test_run_one_missing_folder(schedules_file, workdir, monkeypatch, tmp_path):
    """If the folder was deleted, the run should record an error, not crash."""
    import organizer
    monkeypatch.setattr(organizer, "LOG_DIR", tmp_path / "logs")
    (tmp_path / "logs").mkdir()

    entry = sch.add_schedule(str(workdir))
    # Delete the folder
    workdir.rmdir()
    result = sch.run_schedule_now(entry["id"])
    assert result["last_error"] is not None
    assert "NotADirectoryError" in result["last_error"]


def test_service_starts_and_stops(schedules_file):
    svc = sch.SchedulerService(check_interval=999)
    assert svc.running is False
    svc.start()
    assert svc.running is True
    svc.stop()
    assert svc.running is False
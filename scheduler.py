"""Background scheduler — runs organize on folders at fixed intervals."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import yaml

import config_backup
import events
import folder_rules as fr
from organizer import (
    MODE_EXTENSION,
    VALID_MODES,
    execute,
    load_rules,
    scan,
)
from paths import SCHEDULES_FILE
from settings import load_settings


CHECK_INTERVAL = 30


@dataclass
class Schedule:
    id: str
    folder: str
    mode: str = MODE_EXTENSION
    interval_minutes: int = 60
    enabled: bool = True
    last_run: str | None = None
    last_log: str | None = None
    last_moved: int = 0
    last_error: str | None = None


def _load_raw(path: Path | None = None) -> dict:
    path = path or SCHEDULES_FILE
    if not path.exists():
        return {"schedules": []}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {"schedules": []}
    except Exception:
        return {"schedules": []}


def _save_raw(data: dict, path: Path | None = None) -> None:
    path = path or SCHEDULES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def list_schedules(path: Path | None = None) -> list[dict]:
    raw = _load_raw(path)
    schedules = raw.get("schedules") or []
    for s in schedules:
        s["next_run"] = _compute_next_run(s)
    return schedules


def _compute_next_run(s: dict) -> str | None:
    if not s.get("enabled", True):
        return None
    last = s.get("last_run")
    interval = int(s.get("interval_minutes", 60))
    if not last:
        return "due now"
    try:
        last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return "due now"
    next_dt = last_dt + timedelta(minutes=interval)
    now = datetime.now()
    if next_dt <= now:
        return "due now"
    return next_dt.strftime("%Y-%m-%d %H:%M:%S")


def add_schedule(folder: str, mode: str = MODE_EXTENSION, interval_minutes: int = 60,
                 path: Path | None = None) -> dict:
    folder = str(Path(folder).expanduser().resolve())
    if not Path(folder).is_dir():
        raise NotADirectoryError(f"Not a folder: {folder}")
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode: {mode}")
    if interval_minutes < 1:
        raise ValueError("interval_minutes must be >= 1")

    raw = _load_raw(path)
    entry = {
        "id": uuid.uuid4().hex[:8],
        "folder": folder,
        "mode": mode,
        "interval_minutes": int(interval_minutes),
        "enabled": True,
        "last_run": None,
        "last_log": None,
        "last_moved": 0,
        "last_error": None,
    }
    raw.setdefault("schedules", []).append(entry)
    _save_raw(raw, path)
    events.publish("schedule_added", {"id": entry["id"], "folder": folder})
    return entry


def update_schedule(schedule_id: str, partial: dict, path: Path | None = None) -> dict:
    raw = _load_raw(path)
    schedules = raw.get("schedules") or []
    for s in schedules:
        if s.get("id") == schedule_id:
            if "mode" in partial and partial["mode"] not in VALID_MODES:
                raise ValueError(f"Invalid mode: {partial['mode']}")
            if "interval_minutes" in partial:
                v = int(partial["interval_minutes"])
                if v < 1:
                    raise ValueError("interval_minutes must be >= 1")
                s["interval_minutes"] = v
            if "enabled" in partial:
                s["enabled"] = bool(partial["enabled"])
            if "mode" in partial:
                s["mode"] = partial["mode"]
            _save_raw(raw, path)
            events.publish("schedule_updated", {"id": schedule_id})
            return s
    raise KeyError(f"Schedule not found: {schedule_id}")


def remove_schedule(schedule_id: str, path: Path | None = None) -> None:
    raw = _load_raw(path)
    schedules = raw.get("schedules") or []
    before = len(schedules)
    raw["schedules"] = [s for s in schedules if s.get("id") != schedule_id]
    if len(raw["schedules"]) == before:
        raise KeyError(f"Schedule not found: {schedule_id}")
    _save_raw(raw, path)
    events.publish("schedule_removed", {"id": schedule_id})


def run_schedule_now(schedule_id: str, path: Path | None = None) -> dict:
    return _run_one(schedule_id, path)


def _run_one(schedule_id: str, path: Path | None = None) -> dict:
    raw = _load_raw(path)
    schedules = raw.get("schedules") or []
    target = next((s for s in schedules if s.get("id") == schedule_id), None)
    if target is None:
        raise KeyError(f"Schedule not found: {schedule_id}")

    folder = Path(target["folder"])
    mode = target.get("mode", MODE_EXTENSION)
    s = load_settings()

    try:
        rules = fr.resolve_rules_for(folder, load_rules())
        plan = scan(
            folder,
            rules=rules,
            mode=mode,
            date_format=s.date_format,
            skip_names=set(s.skip_names),
            skip_prefixes=tuple(s.skip_prefixes),
        )
        if plan.total == 0:
            target["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            target["last_log"] = None
            target["last_moved"] = 0
            target["last_error"] = None
        else:
            log_path = execute(plan)
            target["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            target["last_log"] = log_path.name
            target["last_moved"] = plan.total
            target["last_error"] = None
            events.publish("schedule_run", {
                "id": schedule_id,
                "folder": str(folder),
                "moved": plan.total,
                "log": log_path.name,
            })
    except Exception as e:
        target["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        target["last_error"] = f"{type(e).__name__}: {e}"
        target["last_moved"] = 0
        events.publish("schedule_error", {
            "id": schedule_id,
            "folder": str(folder),
            "error": target["last_error"],
        })

    _save_raw(raw, path)
    return target


class SchedulerService:
    def __init__(self, check_interval: int = CHECK_INTERVAL):
        self._check_interval = check_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="scheduler")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._stop.wait(self._check_interval)

    def _tick(self) -> None:
        now = datetime.now()
        for s in list_schedules():
            if not s.get("enabled", True):
                continue
            last = s.get("last_run")
            interval = int(s.get("interval_minutes", 60))
            if last:
                try:
                    last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    last_dt = None
                if last_dt and now < last_dt + timedelta(minutes=interval):
                    continue
            try:
                _run_one(s["id"])
            except Exception:
                pass

        # Every tick also checks if a config backup is due
        try:
            config_backup.run_scheduled_backup()
        except Exception:
            pass
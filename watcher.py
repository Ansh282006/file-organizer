"""Watch a folder and auto-organize files as they arrive."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from watchdog.observers import Observer

import events
import folder_rules as fr
from organizer import (
    MODE_DATE,
    MODE_EXTENSION,
    VALID_MODES,
    Plan,
    PlanItem,
    _unique_name,
    category_for,
    category_for_date,
    execute,
    load_rules,
    should_skip,
)


STABILITY_TIMEOUT = 5.0
STABILITY_INTERVAL = 0.3
STABILITY_ROUNDS = 2


class _Handler(FileSystemEventHandler):
    def __init__(self, folder: Path, mode: str, manager: "WatchManager"):
        self.folder = folder
        self.mode = mode
        self.manager = manager

    def on_created(self, event):
        if event.is_directory:
            return
        if not isinstance(event, FileCreatedEvent):
            return

        src = Path(event.src_path)
        try:
            if src.parent.resolve() != self.folder.resolve():
                return
        except OSError:
            return

        if should_skip(src):
            return

        if not self._wait_stable(src):
            return

        self._organize_one(src)

    def _wait_stable(self, path: Path) -> bool:
        last_size = -1
        stable = 0
        start = time.time()
        while time.time() - start < STABILITY_TIMEOUT:
            if not path.exists():
                return False
            try:
                size = path.stat().st_size
            except OSError:
                return False
            if size == last_size and size > 0:
                stable += 1
                if stable >= STABILITY_ROUNDS:
                    return True
            else:
                stable = 0
                last_size = size
            time.sleep(STABILITY_INTERVAL)
        return True

    def _organize_one(self, src: Path) -> None:
        try:
            if self.mode == MODE_DATE:
                category = category_for_date(src.stat().st_mtime)
            else:
                rules = fr.resolve_rules_for(self.folder, load_rules())
                category = category_for(src.suffix, rules)

            dest_dir = self.folder / category
            raw_dest = dest_dir / src.name
            final_dest, renamed = _unique_name(raw_dest, set())

            item = PlanItem(
                source=src,
                destination=final_dest,
                category=category,
                renamed=renamed,
            )
            plan = Plan(folder=self.folder, items=[item], mode=self.mode)
            log_path = execute(plan)
            self.manager._record_run(src.name, category, log_path.name)
        except Exception as e:
            self.manager._record_error(src.name, f"{type(e).__name__}: {e}")


class WatchManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._observer: Observer | None = None
        self._folder: Path | None = None
        self._mode: str = MODE_EXTENSION
        self._started_at: str | None = None
        self._runs: list[dict] = []
        self._errors: list[dict] = []
        self._total = 0

    def start(self, folder: Path, mode: str = MODE_EXTENSION) -> dict:
        if mode not in VALID_MODES:
            raise ValueError(f"Invalid mode: {mode}")

        folder = Path(folder).expanduser().resolve()
        if not folder.is_dir():
            raise NotADirectoryError(f"Not a folder: {folder}")

        with self._lock:
            self._stop_locked()

            handler = _Handler(folder, mode, self)
            observer = Observer()
            observer.schedule(handler, str(folder), recursive=False)
            observer.start()

            self._observer = observer
            self._folder = folder
            self._mode = mode
            self._started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._runs = []
            self._errors = []
            self._total = 0

        events.publish("watch_started", {
            "folder": str(folder),
            "mode": mode,
            "started_at": self._started_at,
        })
        return self.status()

    def stop(self) -> dict:
        with self._lock:
            was_watching = self._observer is not None
            self._stop_locked()
        if was_watching:
            events.publish("watch_stopped", {})
        return self.status()

    def _stop_locked(self) -> None:
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass
            self._observer = None
        self._folder = None
        self._started_at = None

    def status(self) -> dict:
        with self._lock:
            watching = self._observer is not None
            return {
                "watching": watching,
                "folder": str(self._folder) if self._folder else None,
                "mode": self._mode,
                "started_at": self._started_at,
                "total": self._total,
                "recent_runs": list(self._runs[-20:]),
                "recent_errors": list(self._errors[-10:]),
            }

    def _record_run(self, filename: str, category: str, log_file: str) -> None:
        with self._lock:
            self._total += 1
            entry = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "file": filename,
                "category": category,
                "log": log_file,
            }
            self._runs.append(entry)
        events.publish("watch_run", entry)

    def _record_error(self, filename: str, error: str) -> None:
        with self._lock:
            entry = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "file": filename,
                "error": error,
            }
            self._errors.append(entry)
        events.publish("watch_error", entry)
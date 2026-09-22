"""Core file-organizer logic: scan, plan, execute, undo, rules editing."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from paths import LOG_DIR, RULES_FILE


FALLBACK_CATEGORY = "Misc"

DEFAULT_SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
DEFAULT_SKIP_PREFIXES = (".",)
DEFAULT_DATE_FORMAT = "%Y-%m"

SKIP_NAMES = DEFAULT_SKIP_NAMES
SKIP_PREFIXES = DEFAULT_SKIP_PREFIXES

MODE_EXTENSION = "extension"
MODE_DATE = "date"
VALID_MODES = {MODE_EXTENSION, MODE_DATE}


# ---------- data classes ----------

@dataclass
class Rule:
    name: str
    extensions: set[str]


@dataclass
class PlanItem:
    source: Path
    destination: Path
    category: str
    renamed: bool = False


@dataclass
class Plan:
    folder: Path
    items: list[PlanItem] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    mode: str = MODE_EXTENSION

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def renamed(self) -> int:
        return sum(1 for it in self.items if it.renamed)


# ---------- rules: reading ----------

def load_rules(path: Path | None = None) -> list[Rule]:
    path = path or RULES_FILE
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules: list[Rule] = []
    for name, cfg in raw.items():
        exts = {e.lower() for e in (cfg.get("extensions") or [])}
        rules.append(Rule(name=name, extensions=exts))
    return rules


def category_for(suffix: str, rules: list[Rule]) -> str:
    ext = suffix.lower()
    for rule in rules:
        if ext in rule.extensions:
            return rule.name
    return FALLBACK_CATEGORY


def category_for_date(timestamp: float, date_format: str = DEFAULT_DATE_FORMAT) -> str:
    return datetime.fromtimestamp(timestamp).strftime(date_format)


# ---------- rules: writing ----------

def _load_rules_raw(path: Path | None = None) -> dict:
    path = path or RULES_FILE
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_rules_raw(data: dict, path: Path | None = None) -> None:
    path = path or RULES_FILE
    path.write_text(
        yaml.dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _normalise_ext(ext: str) -> str:
    ext = ext.strip().lower()
    if ext and not ext.startswith("."):
        ext = "." + ext
    return ext


def add_extension(category: str, extension: str) -> None:
    ext = _normalise_ext(extension)
    if not ext:
        raise ValueError("Extension cannot be empty")
    data = _load_rules_raw()
    if category not in data:
        raise KeyError(f"Category not found: {category}")
    exts = set(data[category].get("extensions") or [])
    exts.add(ext)
    data[category]["extensions"] = sorted(exts)
    _write_rules_raw(data)


def remove_extension(category: str, extension: str) -> None:
    ext = _normalise_ext(extension)
    data = _load_rules_raw()
    if category not in data:
        raise KeyError(f"Category not found: {category}")
    exts = set(data[category].get("extensions") or [])
    exts.discard(ext)
    data[category]["extensions"] = sorted(exts)
    _write_rules_raw(data)


def add_category(name: str, extensions: list[str] | None = None) -> None:
    name = name.strip()
    if not name:
        raise ValueError("Category name cannot be empty")
    data = _load_rules_raw()
    if name in data:
        raise ValueError(f"Category already exists: {name}")
    exts = sorted({_normalise_ext(e) for e in (extensions or []) if _normalise_ext(e)})
    data[name] = {"extensions": exts}
    _write_rules_raw(data)


def remove_category(name: str) -> None:
    data = _load_rules_raw()
    if name not in data:
        raise KeyError(f"Category not found: {name}")
    del data[name]
    _write_rules_raw(data)


# ---------- helpers ----------

def should_skip(
    path: Path,
    skip_names: set[str] | None = None,
    skip_prefixes: tuple[str, ...] | None = None,
) -> bool:
    names = skip_names if skip_names is not None else DEFAULT_SKIP_NAMES
    prefixes = skip_prefixes if skip_prefixes is not None else DEFAULT_SKIP_PREFIXES
    name = path.name
    if name in names:
        return True
    return any(name.startswith(p) for p in prefixes)


def _unique_name(dest: Path, taken: set[Path]) -> tuple[Path, bool]:
    if not dest.exists() and dest not in taken:
        return dest, False

    stem, suffix = dest.stem, dest.suffix
    parent = dest.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists() and candidate not in taken:
            return candidate, True
        counter += 1


# ---------- scanning ----------

def scan(
    folder: Path,
    rules: list[Rule] | None = None,
    mode: str = MODE_EXTENSION,
    date_format: str = DEFAULT_DATE_FORMAT,
    skip_names: set[str] | None = None,
    skip_prefixes: tuple[str, ...] | None = None,
) -> Plan:
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a folder: {folder}")

    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode: {mode}")

    rules = rules or load_rules()
    plan = Plan(folder=folder, mode=mode)
    taken: set[Path] = set()

    for entry in sorted(folder.iterdir()):
        if entry.is_dir():
            continue
        if should_skip(entry, skip_names, skip_prefixes):
            plan.skipped.append(entry)
            continue

        if mode == MODE_DATE:
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                plan.skipped.append(entry)
                continue
            category = category_for_date(mtime, date_format)
        else:
            category = category_for(entry.suffix, rules)

        if entry.parent.name == category:
            plan.skipped.append(entry)
            continue

        dest_dir = folder / category
        raw_dest = dest_dir / entry.name
        final_dest, renamed = _unique_name(raw_dest, taken)
        taken.add(final_dest)

        plan.items.append(
            PlanItem(
                source=entry,
                destination=final_dest,
                category=category,
                renamed=renamed,
            )
        )

    return plan


# ---------- execution ----------

def execute(plan: Plan) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"organize_{timestamp}.json"

    moves: list[dict] = []
    errors: list[dict] = []

    for item in plan.items:
        try:
            item.destination.parent.mkdir(parents=True, exist_ok=True)
            item.source.rename(item.destination)
            moves.append({
                "source": str(item.source),
                "destination": str(item.destination),
                "renamed": item.renamed,
            })
        except Exception as e:
            errors.append({
                "source": str(item.source),
                "error": f"{type(e).__name__}: {e}",
            })

    log = {
        "timestamp": timestamp,
        "folder": str(plan.folder),
        "mode": plan.mode,
        "total": len(moves),
        "errors": errors,
        "moves": moves,
    }
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    return log_path


# ---------- logs ----------

def list_logs() -> list[dict]:
    if not LOG_DIR.exists():
        return []

    logs = []
    for f in sorted(LOG_DIR.glob("organize_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        logs.append({
            "file": f.name,
            "timestamp": data.get("timestamp", ""),
            "folder": data.get("folder", ""),
            "mode": data.get("mode", MODE_EXTENSION),
            "total": data.get("total", 0),
            "undone": data.get("undone", False),
        })
    return logs


def latest_undoable_log() -> Path | None:
    for entry in list_logs():
        if not entry["undone"]:
            return LOG_DIR / entry["file"]
    return None


# ---------- undo ----------

def undo(log_path: Path) -> dict:
    log_path = Path(log_path)
    if not log_path.exists():
        raise FileNotFoundError(f"Log not found: {log_path}")

    data = json.loads(log_path.read_text(encoding="utf-8"))

    if data.get("undone"):
        raise ValueError("This log has already been undone")

    restored: list[dict] = []
    errors: list[dict] = []

    for move in reversed(data.get("moves", [])):
        src = Path(move["destination"])
        dst = Path(move["source"])

        if not src.exists():
            errors.append({"source": str(src), "error": "File no longer exists at destination"})
            continue

        if dst.exists():
            errors.append({"source": str(src), "error": f"Original path already occupied: {dst}"})
            continue

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            restored.append({"from": str(src), "to": str(dst)})
        except Exception as e:
            errors.append({"source": str(src), "error": f"{type(e).__name__}: {e}"})

    data["undone"] = True
    data["undone_at"] = datetime.now().strftime("%Y%m%d_%H%M%S")
    data["undo_result"] = {"restored": len(restored), "errors": errors}
    log_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _prune_empty_dirs(data.get("folder"))

    return {"log_file": log_path.name, "restored": len(restored), "errors": errors}


def _prune_empty_dirs(root: str | None) -> None:
    if not root:
        return
    root_path = Path(root)
    if not root_path.is_dir():
        return
    for sub in root_path.iterdir():
        if sub.is_dir() and not any(sub.iterdir()):
            try:
                sub.rmdir()
            except OSError:
                pass


# ---------- CLI preview ----------

def print_plan(plan: Plan) -> None:
    print(f"\n[DIR] {plan.folder}  (mode: {plan.mode})")
    print(f"    {plan.total} file(s) to organize, {len(plan.skipped)} skipped\n")

    if not plan.items:
        print("    (nothing to organize)\n")
        return

    for it in plan.items:
        marker = "* " if it.renamed else "  "
        rel_dest = it.destination.relative_to(plan.folder)
        print(f"  {marker}{it.source.name:<40} -> {rel_dest}")

    if plan.renamed:
        print(f"\n  *  {plan.renamed} file(s) renamed to avoid clashes.")


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    mode = MODE_EXTENSION
    if "--date" in args:
        mode = MODE_DATE
        args.remove("--date")
    target = Path(args[0]) if args else Path.cwd()
    print_plan(scan(target, mode=mode))
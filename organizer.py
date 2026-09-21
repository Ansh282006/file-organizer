"""Core file-organizer logic: scan, plan, execute."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml


RULES_FILE = Path(__file__).parent / "rules.yaml"
LOG_DIR = Path(__file__).parent / "logs"
FALLBACK_CATEGORY = "Misc"

SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
SKIP_PREFIXES = (".",)


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

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def renamed(self) -> int:
        return sum(1 for it in self.items if it.renamed)


# ---------- rules ----------

def load_rules(path: Path = RULES_FILE) -> list[Rule]:
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


# ---------- helpers ----------

def should_skip(path: Path) -> bool:
    name = path.name
    if name in SKIP_NAMES:
        return True
    return any(name.startswith(p) for p in SKIP_PREFIXES)


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

def scan(folder: Path, rules: list[Rule] | None = None) -> Plan:
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a folder: {folder}")

    rules = rules or load_rules()
    plan = Plan(folder=folder)
    taken: set[Path] = set()

    for entry in sorted(folder.iterdir()):
        if entry.is_dir():
            continue
        if should_skip(entry):
            plan.skipped.append(entry)
            continue

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
    """
    Actually move the files in `plan`. Writes a JSON log to logs/.
    Returns the path of the log file.
    """
    LOG_DIR.mkdir(exist_ok=True)
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
        "total": len(moves),
        "errors": errors,
        "moves": moves,
    }
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    return log_path


# ---------- CLI preview ----------

def print_plan(plan: Plan) -> None:
    print(f"\n[DIR] {plan.folder}")
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

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print_plan(scan(target))
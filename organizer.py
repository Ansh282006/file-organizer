"""Core file-organizer logic: scan, plan, and (later) execute moves."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


RULES_FILE = Path(__file__).parent / "rules.yaml"
FALLBACK_CATEGORY = "Misc"

SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
SKIP_PREFIXES = (".",)


@dataclass
class Rule:
    name: str
    extensions: set[str]


@dataclass
class PlanItem:
    source: Path
    destination: Path
    category: str
    renamed: bool = False   # True if we changed the filename to avoid a clash


@dataclass
class Plan:
    folder: Path
    items: list[PlanItem] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)  # already sorted / ignored

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
    """
    If `dest` clashes with an existing file OR with another item already
    claimed in this plan, append _1, _2, ... until it doesn't.

    Returns (final_path, was_renamed).
    """
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
    """
    Walk the top level of `folder` (non-recursive) and build a Plan.
    Subfolders are left alone; files already in their target folder are skipped.
    """
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

        # Already in the right category folder? Skip it.
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


# ---------- CLI preview ----------

def print_plan(plan: Plan) -> None:
    print(f"\n📁  {plan.folder}")
    print(f"    {plan.total} file(s) to organize, {len(plan.skipped)} skipped\n")

    if not plan.items:
        print("    (nothing to organize)\n")
        return

    for it in plan.items:
        marker = "✎ " if it.renamed else "  "
        rel_dest = it.destination.relative_to(plan.folder)
        print(f"  {marker}{it.source.name:<40} → {rel_dest}")

    if plan.renamed:
        print(f"\n  ✎  {plan.renamed} file(s) renamed to avoid clashes.")


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print_plan(scan(target))
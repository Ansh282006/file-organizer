"""Find large files inside a folder (recursive)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from organizer import Plan, PlanItem, _unique_name


QUARANTINE_DIR = "_large_files"
DEFAULT_MIN_MB = 100
MAX_RESULTS = 500


@dataclass
class LargeFile:
    path: Path
    name: str
    rel_path: str
    size: int
    mtime: float


def _walk(
    root: Path,
    skip_names: set[str],
    skip_prefixes: tuple[str, ...],
    skip_dirs: set[str],
):
    """Yield files under root, skipping hidden / ignored entries."""
    for entry in root.iterdir():
        name = entry.name
        if name in skip_names:
            continue
        if any(name.startswith(p) for p in skip_prefixes):
            continue
        if entry.is_dir():
            if name in skip_dirs:
                continue
            yield from _walk(entry, skip_names, skip_prefixes, skip_dirs)
        elif entry.is_file():
            yield entry


def find_large_files(
    folder: Path,
    min_bytes: int = DEFAULT_MIN_MB * 1024 * 1024,
    skip_names: set[str] | None = None,
    skip_prefixes: tuple[str, ...] | None = None,
    skip_dirs: set[str] | None = None,
    max_results: int = MAX_RESULTS,
) -> dict:
    """
    Recursively scan folder and return files >= min_bytes.
    Sorted by size descending. Capped at max_results.
    """
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a folder: {folder}")

    skip_names = skip_names or set()
    skip_prefixes = skip_prefixes or ()
    skip_dirs = skip_dirs or {QUARANTINE_DIR, "_duplicates"}

    if min_bytes < 0:
        raise ValueError("min_bytes must be >= 0")

    results: list[LargeFile] = []
    total_scanned = 0
    total_bytes_scanned = 0

    for entry in _walk(folder, skip_names, skip_prefixes, skip_dirs):
        total_scanned += 1
        try:
            st = entry.stat()
        except OSError:
            continue
        total_bytes_scanned += st.st_size
        if st.st_size < min_bytes:
            continue

        try:
            rel = entry.relative_to(folder).as_posix()
        except ValueError:
            rel = str(entry)

        results.append(LargeFile(
            path=entry,
            name=entry.name,
            rel_path=rel,
            size=st.st_size,
            mtime=st.st_mtime,
        ))

    results.sort(key=lambda f: f.size, reverse=True)
    truncated = len(results) > max_results
    results = results[:max_results]

    return {
        "folder": str(folder),
        "min_bytes": min_bytes,
        "total_scanned": total_scanned,
        "total_bytes_scanned": total_bytes_scanned,
        "matched": len(results),
        "total_matched_bytes": sum(f.size for f in results),
        "truncated": truncated,
        "files": [
            {
                "path": str(f.path),
                "name": f.name,
                "rel_path": f.rel_path,
                "size": f.size,
                "mtime": f.mtime,
            }
            for f in results
        ],
    }


def plan_quarantine(folder: Path, files: list[dict]) -> Plan:
    """Build a Plan that moves the given files into _large_files/."""
    folder = Path(folder).expanduser().resolve()
    plan = Plan(folder=folder, mode="large_files")
    taken: set[Path] = set()
    quarantine = folder / QUARANTINE_DIR

    for f in files:
        src = Path(f["path"])
        # Preserve relative structure inside _large_files/ to avoid name clashes
        rel = f.get("rel_path") or src.name
        raw_dest = quarantine / rel
        final_dest, renamed = _unique_name(raw_dest, taken)
        taken.add(final_dest)
        plan.items.append(PlanItem(
            source=src,
            destination=final_dest,
            category=QUARANTINE_DIR,
            renamed=renamed,
        ))

    return plan
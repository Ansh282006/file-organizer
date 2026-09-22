"""Duplicate file detection — content-hash based."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from organizer import Plan, PlanItem, _unique_name


CHUNK_SIZE = 65536  # 64 KB
QUARANTINE_DIR = "_duplicates"


@dataclass
class DuplicateFile:
    path: Path
    name: str
    size: int
    mtime: float


@dataclass
class DuplicateGroup:
    hash: str
    size: int
    files: list[DuplicateFile]

    @property
    def wasted_bytes(self) -> int:
        return self.size * (len(self.files) - 1)


def _hash_file(path: Path, chunk_size: int = CHUNK_SIZE) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def find_duplicates(
    folder: Path,
    skip_names: set[str] | None = None,
    skip_prefixes: tuple[str, ...] | None = None,
    skip_dirs: set[str] | None = None,
) -> dict:
    """
    Scan folder (top level only) and return duplicate groups.

    Algorithm:
      1. Group files by size (fast filter).
      2. For sizes with >1 file, hash full content.
      3. Keep groups with >1 hash match.

    Empty files are ignored. Subfolders are ignored.
    """
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a folder: {folder}")

    skip_names = skip_names or set()
    skip_prefixes = skip_prefixes or ()
    skip_dirs = skip_dirs or {QUARANTINE_DIR}

    # 1. Group by size
    by_size: dict[int, list[Path]] = {}
    total = 0
    for entry in folder.iterdir():
        if entry.is_dir():
            continue
        if entry.name in skip_names:
            continue
        if any(entry.name.startswith(p) for p in skip_prefixes):
            continue
        try:
            size = entry.stat().st_size
        except OSError:
            continue
        if size == 0:
            continue
        by_size.setdefault(size, []).append(entry)
        total += 1

    # 2. Hash only files whose size collides
    by_hash: dict[str, list[Path]] = {}
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        for p in paths:
            try:
                h = _hash_file(p)
            except OSError:
                continue
            by_hash.setdefault(h, []).append(p)

    # 3. Build groups
    groups: list[DuplicateGroup] = []
    for h, paths in by_hash.items():
        if len(paths) < 2:
            continue
        files = []
        for p in paths:
            try:
                st = p.stat()
            except OSError:
                continue
            files.append(DuplicateFile(
                path=p, name=p.name, size=st.st_size, mtime=st.st_mtime,
            ))
        files.sort(key=lambda f: f.mtime, reverse=True)  # newest first
        groups.append(DuplicateGroup(hash=h, size=files[0].size, files=files))

    groups.sort(key=lambda g: g.wasted_bytes, reverse=True)

    return {
        "folder": str(folder),
        "total_files": total,
        "total_groups": len(groups),
        "wasted_bytes": sum(g.wasted_bytes for g in groups),
        "groups": [
            {
                "hash": g.hash,
                "size": g.size,
                "wasted_bytes": g.wasted_bytes,
                "files": [
                    {
                        "path": str(f.path),
                        "name": f.name,
                        "rel_path": f.path.relative_to(folder).as_posix(),
                        "size": f.size,
                        "mtime": f.mtime,
                    }
                    for f in g.files
                ],
            }
            for g in groups
        ],
    }


def plan_quarantine(folder: Path, groups: list[dict]) -> Plan:
    """
    Build a Plan that moves every duplicate EXCEPT the newest into _duplicates/.
    Pass the `groups` array returned by find_duplicates().
    """
    folder = Path(folder).expanduser().resolve()
    plan = Plan(folder=folder, mode="duplicates")
    taken: set[Path] = set()
    quarantine = folder / QUARANTINE_DIR

    for group in groups:
        files = group.get("files", [])
        # files[0] is newest (kept). files[1:] get moved.
        for f in files[1:]:
            src = Path(f["path"])
            raw_dest = quarantine / src.name
            final_dest, renamed = _unique_name(raw_dest, taken)
            taken.add(final_dest)
            plan.items.append(PlanItem(
                source=src,
                destination=final_dest,
                category=QUARANTINE_DIR,
                renamed=renamed,
            ))

    return plan
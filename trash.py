"""Send files to the OS recycle bin / trash."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from send2trash import send2trash as _send2trash
    try:
        from send2trash.exceptions import TrashPermissionError
    except ImportError:
        TrashPermissionError = OSError
    _SEND2TRASH_AVAILABLE = True
except ImportError:
    _SEND2TRASH_AVAILABLE = False
    TrashPermissionError = OSError


def _in_container() -> bool:
    """Detect Docker / Podman."""
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def is_supported() -> bool:
    """True if send2trash is available AND we're not inside a container."""
    if _in_container():
        return False
    return _SEND2TRASH_AVAILABLE


@dataclass
class TrashResult:
    path: str
    success: bool
    error: str | None = None


def send_to_trash(path: Path) -> TrashResult:
    p = Path(path)

    if _in_container():
        return TrashResult(str(p), False, "OS trash disabled inside container — use Quarantine instead")

    if not _SEND2TRASH_AVAILABLE:
        return TrashResult(str(p), False, "send2trash not installed")

    if not p.exists():
        return TrashResult(str(p), False, "file does not exist")

    try:
        _send2trash(str(p))
        return TrashResult(str(p), True, None)
    except TrashPermissionError as e:
        return TrashResult(str(p), False, f"permission denied: {e}")
    except OSError as e:
        return TrashResult(str(p), False, f"{type(e).__name__}: {e}")
    except Exception as e:
        return TrashResult(str(p), False, f"{type(e).__name__}: {e}")


def trash_many(paths: list[Path]) -> dict:
    results = [send_to_trash(p) for p in paths]
    ok = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    return {
        "trashed": len(ok),
        "failed": len(failed),
        "results": [
            {"path": r.path, "success": r.success, "error": r.error}
            for r in results
        ],
    }
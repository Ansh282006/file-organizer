"""Extract a still frame from a video using ffmpeg and cache it as JPEG.

Gracefully degrades: if ffmpeg isn't installed, `is_supported()` returns
False and the caller falls back to a plain file-type badge.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from threading import Lock

from PIL import Image


VIDEO_EXTS = {
    ".mp4", ".m4v", ".mov", ".avi", ".mkv", ".webm",
    ".wmv", ".flv", ".mpg", ".mpeg", ".3gp",
}

THUMB_SIZE = (96, 96)
MAX_CACHE_ENTRIES = 200
JPEG_QUALITY = 75
EXTRACT_TIMEOUT = 10        # seconds per ffmpeg call
SEEK_SECONDS = "2"          # skip past black intro frames

_cache: OrderedDict[tuple[str, float], bytes] = OrderedDict()
_lock = Lock()


# ---------- public API ----------

def is_supported() -> bool:
    """True if ffmpeg is available on PATH."""
    return shutil.which("ffmpeg") is not None


def is_video(path: Path) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTS


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def generate_video_thumbnail(
    path: Path,
    size: tuple[int, int] = THUMB_SIZE,
) -> bytes:
    """
    Extract a frame from `path` and return it as JPEG bytes.
    Raises FileNotFoundError, ValueError, or ffmpeg-related errors.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")
    if not is_video(path):
        raise ValueError(f"Not a supported video: {path.suffix}")
    if not is_supported():
        raise ValueError("ffmpeg not installed")

    try:
        mtime = path.stat().st_mtime
    except OSError as e:
        raise ValueError(f"Cannot stat file: {e}") from e

    key = (str(path), mtime)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    data = _extract_and_resize(path, size)
    _cache_put(key, data)
    return data


# ---------- internals ----------

def _cache_get(key: tuple[str, float]) -> bytes | None:
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    return None


def _cache_put(key: tuple[str, float], value: bytes) -> None:
    with _lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > MAX_CACHE_ENTRIES:
            _cache.popitem(last=False)


def _extract_and_resize(path: Path, size: tuple[int, int]) -> bytes:
    """Run ffmpeg to a temp file, then Pillow-resize to JPEG bytes."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        _run_ffmpeg(path, tmp_path, seek=SEEK_SECONDS)
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            # Retry without seeking — the video is probably shorter than SEEK_SECONDS
            _run_ffmpeg(path, tmp_path, seek=None)

        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            raise ValueError("ffmpeg produced no frame")

        with Image.open(tmp_path) as img:
            img.thumbnail(size, Image.LANCZOS)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            return buf.getvalue()

    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _run_ffmpeg(input_path: Path, output_path: Path, seek: str | None) -> None:
    cmd = ["ffmpeg"]
    if seek is not None:
        cmd += ["-ss", seek]
    cmd += [
        "-i", str(input_path),
        "-frames:v", "1",
        "-f", "image2",
        "-y",
        str(output_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=EXTRACT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise ValueError("ffmpeg timed out")
    except FileNotFoundError:
        raise ValueError("ffmpeg not installed")

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")[:300]
        raise ValueError(f"ffmpeg failed: {stderr}")
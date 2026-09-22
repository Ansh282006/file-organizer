"""Generate and cache small thumbnails for preview tables."""

from __future__ import annotations

from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from threading import Lock

from PIL import Image, ImageOps


THUMB_SIZE = (96, 96)
MAX_CACHE_ENTRIES = 500
JPEG_QUALITY = 75

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".bmp", ".tiff", ".tif", ".heic", ".heif",
}

# LRU cache: key = (path_str, mtime) → thumbnail bytes
_cache: OrderedDict[tuple[str, float], bytes] = OrderedDict()
_lock = Lock()


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


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


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def generate_thumbnail(path: Path, size: tuple[int, int] = THUMB_SIZE) -> bytes:
    """
    Return JPEG bytes of a thumbnail for the given image path.
    Raises FileNotFoundError if the file doesn't exist.
    Raises ValueError if the file isn't a supported image or can't be decoded.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")
    if not is_image(path):
        raise ValueError(f"Not a supported image: {path.suffix}")

    try:
        mtime = path.stat().st_mtime
    except OSError as e:
        raise ValueError(f"Cannot stat file: {e}") from e

    key = (str(path), mtime)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail(size, Image.LANCZOS)

            # Convert anything to RGB for JPEG output
            if img.mode not in ("RGB", "L"):
                if img.mode == "RGBA":
                    bg = Image.new("RGB", img.size, (23, 26, 35))
                    bg.paste(img, mask=img.split()[3])
                    img = bg
                else:
                    img = img.convert("RGB")

            buf = BytesIO()
            img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            data = buf.getvalue()
    except Exception as e:
        raise ValueError(f"Failed to decode image: {type(e).__name__}: {e}") from e

    _cache_put(key, data)
    return data
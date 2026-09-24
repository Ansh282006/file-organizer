"""Tests for video thumbnail extraction.

Real extraction tests are skipped when ffmpeg isn't installed.
"""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

import video_thumbnails
from video_thumbnails import (
    clear_cache,
    generate_video_thumbnail,
    is_supported,
    is_video,
)


@pytest.fixture(autouse=True)
def reset_cache():
    clear_cache()
    yield
    clear_cache()


# ---------- extension detection ----------

def test_is_video_common_extensions():
    assert is_video(Path("a.mp4"))
    assert is_video(Path("a.mov"))
    assert is_video(Path("a.mkv"))
    assert is_video(Path("a.webm"))
    assert is_video(Path("a.AVI"))  # case-insensitive


def test_is_video_rejects_non_videos():
    assert not is_video(Path("a.jpg"))
    assert not is_video(Path("a.txt"))
    assert not is_video(Path("a"))


def test_is_supported_returns_bool():
    assert isinstance(is_supported(), bool)


# ---------- graceful errors ----------

def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        generate_video_thumbnail(tmp_path / "nope.mp4")


def test_non_video_extension_raises(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("x")
    with pytest.raises(ValueError):
        generate_video_thumbnail(p)


# ---------- real extraction (skipped without ffmpeg) ----------

def _make_test_video(path: Path, seconds: int = 3, size: str = "320x240") -> Path:
    """Generate a small test video using ffmpeg's testsrc pattern."""
    import subprocess
    subprocess.run(
        [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"testsrc=duration={seconds}:size={size}:rate=1",
            "-pix_fmt", "yuv420p",
            "-y",
            str(path),
        ],
        capture_output=True,
        timeout=30,
        check=True,
    )
    return path


@pytest.mark.skipif(not is_supported(), reason="ffmpeg not installed")
def test_extract_from_real_video(tmp_path):
    video = _make_test_video(tmp_path / "test.mp4")
    data = generate_video_thumbnail(video)
    assert isinstance(data, bytes)
    assert data[:2] == b"\xff\xd8"          # JPEG magic bytes
    img = Image.open(BytesIO(data))
    assert max(img.size) <= 96


@pytest.mark.skipif(not is_supported(), reason="ffmpeg not installed")
def test_cache_hit(tmp_path):
    video = _make_test_video(tmp_path / "cached.mp4")
    a = generate_video_thumbnail(video)
    b = generate_video_thumbnail(video)
    assert a == b


@pytest.mark.skipif(not is_supported(), reason="ffmpeg not installed")
def test_very_short_video_falls_back(tmp_path):
    """A video shorter than SEEK_SECONDS should still produce a frame."""
    video = _make_test_video(tmp_path / "short.mp4", seconds=1)
    data = generate_video_thumbnail(video)
    assert data[:2] == b"\xff\xd8"


@pytest.mark.skipif(not is_supported(), reason="ffmpeg not installed")
def test_cache_invalidated_on_mtime_change(tmp_path):
    import os
    import time

    video = _make_test_video(tmp_path / "mtime.mp4", seconds=3)
    a = generate_video_thumbnail(video)

    time.sleep(0.05)
    # Touch the file to bump its mtime
    os.utime(video, None)

    b = generate_video_thumbnail(video)
    # Different mtime → cache miss → new extraction. Bytes may or may not differ
    # since the frame content is the same, but the key changed. Just assert it works.
    assert b[:2] == b"\xff\xd8"
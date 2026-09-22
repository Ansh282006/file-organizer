"""Tests for thumbnail generation."""

import pytest
from PIL import Image

import thumbnails
from thumbnails import clear_cache, generate_thumbnail, is_image


@pytest.fixture(autouse=True)
def reset_cache():
    clear_cache()
    yield
    clear_cache()


def make_image(path, size=(200, 150), color=(255, 0, 0), fmt=None):
    img = Image.new("RGB", size, color)
    img.save(path, format=fmt)
    return path


def test_is_image_extensions():
    assert is_image(__import__("pathlib").Path("a.jpg"))
    assert is_image(__import__("pathlib").Path("a.PNG"))
    assert not is_image(__import__("pathlib").Path("a.txt"))
    assert not is_image(__import__("pathlib").Path("a.pdf"))


def test_generate_basic(tmp_path):
    p = make_image(tmp_path / "test.png", fmt="PNG")
    data = generate_thumbnail(p)
    assert isinstance(data, bytes)
    assert len(data) > 0
    # JPEG magic bytes
    assert data[:2] == b"\xff\xd8"


def test_thumbnail_size(tmp_path):
    p = make_image(tmp_path / "big.jpg", size=(800, 600), fmt="JPEG")
    data = generate_thumbnail(p, size=(64, 64))
    img = Image.open(__import__("io").BytesIO(data))
    assert max(img.size) <= 64


def test_rgba_converts_to_rgb(tmp_path):
    p = tmp_path / "rgba.png"
    Image.new("RGBA", (100, 100), (255, 0, 0, 128)).save(p)
    data = generate_thumbnail(p)
    img = Image.open(__import__("io").BytesIO(data))
    assert img.mode == "RGB"


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        generate_thumbnail(tmp_path / "nope.jpg")


def test_non_image_raises(tmp_path):
    p = tmp_path / "file.txt"
    p.write_text("hello")
    with pytest.raises(ValueError):
        generate_thumbnail(p)


def test_cache_hit(tmp_path):
    p = make_image(tmp_path / "cached.png", fmt="PNG")
    first = generate_thumbnail(p)
    second = generate_thumbnail(p)
    # Cached bytes should be identical object (or at least identical bytes)
    assert first is second or first == second


def test_cache_invalidates_on_mtime_change(tmp_path):
    import time, os
    p = make_image(tmp_path / "change.png", size=(100, 100), color=(255, 0, 0), fmt="PNG")
    first = generate_thumbnail(p)

    # Change the file content and mtime
    time.sleep(0.05)
    make_image(p, size=(100, 100), color=(0, 255, 0), fmt="PNG")
    os.utime(p, None)  # bump mtime to now

    second = generate_thumbnail(p)
    assert first != second


def test_corrupt_image_raises(tmp_path):
    p = tmp_path / "corrupt.png"
    p.write_bytes(b"not a real png")
    with pytest.raises(ValueError):
        generate_thumbnail(p)
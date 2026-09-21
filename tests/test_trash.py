"""Tests for OS trash integration.

These tests are mostly shape checks — the actual send2trash call is
mocked so we don't spam the developer's real Recycle Bin.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

import trash
from trash import send_to_trash, trash_many, is_supported


def test_is_supported_returns_bool():
    assert isinstance(is_supported(), bool)


def test_missing_file_reports_error(tmp_path):
    result = send_to_trash(tmp_path / "nope.txt")
    assert result.success is False
    assert result.error == "file does not exist"


def test_trash_many_empty_list():
    result = trash_many([])
    assert result["trashed"] == 0
    assert result["failed"] == 0
    assert result["results"] == []


def test_trash_many_reports_shape(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("x")
    b.write_text("y")
    result = trash_many([a, b])
    assert "trashed" in result
    assert "failed" in result
    assert "results" in result
    assert len(result["results"]) == 2
    for r in result["results"]:
        assert "path" in r
        assert "success" in r
        assert "error" in r


def test_send_uses_send2trash_when_available(tmp_path, monkeypatch):
    """Mock send2trash and verify it's called with the right path."""
    if not is_supported():
        pytest.skip("send2trash not installed")

    called = {}

    def fake_send(p):
        called["path"] = p

    monkeypatch.setattr(trash, "_send2trash", fake_send)

    f = tmp_path / "file.txt"
    f.write_text("x")
    result = send_to_trash(f)

    assert result.success is True
    assert result.error is None
    assert called["path"] == str(f)


def test_send_handles_exception(tmp_path, monkeypatch):
    if not is_supported():
        pytest.skip("send2trash not installed")

    def fake_send(p):
        raise OSError("disk full")

    monkeypatch.setattr(trash, "_send2trash", fake_send)

    f = tmp_path / "file.txt"
    f.write_text("x")
    result = send_to_trash(f)

    assert result.success is False
    assert "OSError" in result.error or "disk full" in result.error


def test_trash_many_partial_failure(tmp_path, monkeypatch):
    if not is_supported():
        pytest.skip("send2trash not installed")

    def fake_send(p):
        if p.endswith("bad.txt"):
            raise OSError("nope")

    monkeypatch.setattr(trash, "_send2trash", fake_send)

    good = tmp_path / "good.txt"
    bad = tmp_path / "bad.txt"
    good.write_text("x")
    bad.write_text("y")

    result = trash_many([good, bad])
    assert result["trashed"] == 1
    assert result["failed"] == 1
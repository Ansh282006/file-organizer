"""Tests for settings persistence."""

import pytest

import settings as settings_mod
from settings import (
    Settings,
    load_settings,
    save_settings,
    update_settings,
    DEFAULT_SKIP_NAMES,
    DEFAULT_SKIP_PREFIXES,
)


@pytest.fixture
def settings_path(tmp_path, monkeypatch):
    p = tmp_path / "settings.yaml"
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", p)
    return p


def test_load_defaults_when_missing(settings_path):
    s = load_settings()
    assert s.default_mode == "extension"
    assert s.date_format == "%Y-%m"
    assert s.skip_names == DEFAULT_SKIP_NAMES
    assert s.skip_prefixes == DEFAULT_SKIP_PREFIXES


def test_save_and_load(settings_path):
    s = Settings(default_mode="date", date_format="%Y-%m-%d",
                 skip_names=["a"], skip_prefixes=["."])
    save_settings(s)
    loaded = load_settings()
    assert loaded.default_mode == "date"
    assert loaded.date_format == "%Y-%m-%d"
    assert loaded.skip_names == ["a"]


def test_update_partial(settings_path):
    update_settings({"default_mode": "date"})
    s = load_settings()
    assert s.default_mode == "date"
    # Other fields preserved
    assert s.date_format == "%Y-%m"


def test_update_invalid_mode(settings_path):
    with pytest.raises(ValueError):
        update_settings({"default_mode": "banana"})


def test_update_skip_names(settings_path):
    update_settings({"skip_names": ["foo", "bar"]})
    s = load_settings()
    assert s.skip_names == ["foo", "bar"]


def test_update_skip_names_filters_empty(settings_path):
    update_settings({"skip_names": ["foo", "", "  ", "bar"]})
    s = load_settings()
    assert s.skip_names == ["foo", "bar"]


def test_update_skip_names_must_be_list(settings_path):
    with pytest.raises(ValueError):
        update_settings({"skip_names": "not a list"})


def test_corrupt_settings_file_returns_defaults(settings_path, tmp_path):
    settings_path.write_text("::: not yaml :::", encoding="utf-8")
    s = load_settings()
    assert s.default_mode == "extension"
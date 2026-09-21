"""Tests for config export / import / reset."""

import json

import pytest
import yaml

import config_io
import organizer
import scheduler as scheduler_mod
import settings as settings_mod


@pytest.fixture
def isolate_config(tmp_path, monkeypatch):
    """Point every config path at a temp folder so tests don't touch real files."""
    rules = tmp_path / "rules.yaml"
    stg = tmp_path / "settings.yaml"
    sch = tmp_path / "schedules.yaml"

    rules.write_text(
        "Images:\n  extensions: [.jpg, .png]\nDocuments:\n  extensions: [.pdf]\n",
        encoding="utf-8",
    )
    stg.write_text("default_mode: extension\ndate_format: '%Y-%m'\n", encoding="utf-8")
    sch.write_text("schedules: []\n", encoding="utf-8")

    monkeypatch.setattr(organizer, "RULES_FILE", rules)
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", stg)
    monkeypatch.setattr(scheduler_mod, "SCHEDULES_FILE", sch)

    return {"rules": rules, "settings": stg, "schedules": sch}


def test_export_basic(isolate_config):
    bundle = config_io.export_bundle()
    assert bundle["version"] == 1
    assert "exported_at" in bundle
    assert "Images" in bundle["rules"]
    assert bundle["settings"]["default_mode"] == "extension"
    assert bundle["schedules"]["schedules"] == []


def test_import_replace_rules(isolate_config):
    bundle = {
        "version": 1,
        "rules": {"Videos": {"extensions": [".mp4"]}},
        "settings": {},
        "schedules": {"schedules": []},
    }
    config_io.import_bundle(bundle, strategy="replace")
    rules = yaml.safe_load(isolate_config["rules"].read_text())
    assert "Videos" in rules
    assert "Images" not in rules  # replaced


def test_import_merge_rules(isolate_config):
    bundle = {
        "version": 1,
        "rules": {
            "Images": {"extensions": [".bmp"]},   # adds to existing
            "Videos": {"extensions": [".mp4"]},   # new category
        },
    }
    config_io.import_bundle(bundle, strategy="merge")
    rules = yaml.safe_load(isolate_config["rules"].read_text())
    assert ".bmp" in rules["Images"]["extensions"]
    assert ".jpg" in rules["Images"]["extensions"]  # preserved
    assert "Videos" in rules


def test_import_replace_settings(isolate_config):
    bundle = {
        "version": 1,
        "settings": {
            "default_mode": "date",
            "date_format": "%Y-%m-%d",
            "skip_names": ["skip.txt"],
            "skip_prefixes": ["~"],
        },
    }
    config_io.import_bundle(bundle, strategy="replace")
    s = yaml.safe_load(isolate_config["settings"].read_text())
    assert s["default_mode"] == "date"
    assert s["date_format"] == "%Y-%m-%d"


def test_import_invalid_settings_rejected(isolate_config):
    bundle = {
        "version": 1,
        "settings": {"skip_names": "not a list"},
    }
    applied = config_io.import_bundle(bundle, strategy="replace")
    assert applied["settings"] is False
    # Original file untouched
    s = yaml.safe_load(isolate_config["settings"].read_text())
    assert s["default_mode"] == "extension"


def test_import_replace_schedules(isolate_config):
    bundle = {
        "version": 1,
        "schedules": {
            "schedules": [
                {"folder": "/tmp/a", "mode": "extension", "interval_minutes": 30, "enabled": True},
                {"folder": "/tmp/b", "mode": "date", "interval_minutes": 60, "enabled": False},
            ]
        },
    }
    applied = config_io.import_bundle(bundle, strategy="replace")
    assert applied["schedules"] == 2

    data = yaml.safe_load(isolate_config["schedules"].read_text())
    folders = [s["folder"] for s in data["schedules"]]
    assert "/tmp/a" in folders
    assert "/tmp/b" in folders
    # Fresh IDs and cleared run history
    for s in data["schedules"]:
        assert s["id"]
        assert s["last_run"] is None


def test_import_merge_schedules_skips_dupe_folders(isolate_config):
    # Seed with one existing schedule
    isolate_config["schedules"].write_text(
        yaml.dump({"schedules": [{"id": "abc12345", "folder": "/tmp/a", "mode": "extension",
                                  "interval_minutes": 30, "enabled": True,
                                  "last_run": None, "last_log": None,
                                  "last_moved": 0, "last_error": None}]}),
        encoding="utf-8",
    )
    bundle = {
        "version": 1,
        "schedules": {
            "schedules": [
                {"folder": "/tmp/a", "mode": "extension", "interval_minutes": 30},
                {"folder": "/tmp/c", "mode": "extension", "interval_minutes": 60},
            ]
        },
    }
    applied = config_io.import_bundle(bundle, strategy="merge")
    assert applied["schedules"] == 1  # /tmp/a skipped, /tmp/c added


def test_invalid_strategy(isolate_config):
    with pytest.raises(ValueError):
        config_io.import_bundle({}, strategy="banana")


def test_non_dict_bundle(isolate_config):
    with pytest.raises(ValueError):
        config_io.import_bundle("not a dict")


def test_reset_restores_defaults(isolate_config):
    # Dump some junk in first
    isolate_config["rules"].write_text("Junk:\n  extensions: [.xyz]\n", encoding="utf-8")
    isolate_config["settings"].write_text("default_mode: date\n", encoding="utf-8")

    config_io.reset_all()

    rules = yaml.safe_load(isolate_config["rules"].read_text())
    assert "Junk" not in rules
    assert "Images" in rules
    assert "Documents" in rules

    s = yaml.safe_load(isolate_config["settings"].read_text())
    assert s["default_mode"] == "extension"

    sch = yaml.safe_load(isolate_config["schedules"].read_text())
    assert sch["schedules"] == []


def test_round_trip(isolate_config):
    """Export → import → export should be equivalent."""
    bundle1 = config_io.export_bundle()
    config_io.import_bundle(bundle1, strategy="replace")
    bundle2 = config_io.export_bundle()
    # Ignore timestamp
    del bundle1["exported_at"]
    del bundle2["exported_at"]
    assert bundle1 == bundle2
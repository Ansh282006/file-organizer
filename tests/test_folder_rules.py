"""Tests for per-folder rule overrides."""

from pathlib import Path

import pytest

import folder_rules
from folder_rules import (
    get_folder_rule,
    list_folder_rules,
    remove_folder_rule,
    resolve_rules_for,
    set_folder_rule,
)
from organizer import Rule


@pytest.fixture
def fr_file(tmp_path, monkeypatch):
    p = tmp_path / "folder_rules.yaml"
    monkeypatch.setattr(folder_rules, "FOLDER_RULES_FILE", p)
    return p


def make_rule(name, exts):
    return Rule(name=name, extensions=set(exts))


def test_list_empty(fr_file):
    assert list_folder_rules() == []


def test_set_and_get(fr_file, tmp_path):
    folder = tmp_path / "Downloads"
    folder.mkdir()
    set_folder_rule(folder, {"Images": [".jpg", ".png"]})
    entry = get_folder_rule(folder)
    assert entry is not None
    assert entry["rules"]["Images"] == [".jpg", ".png"]


def test_set_upserts(fr_file, tmp_path):
    folder = tmp_path / "Downloads"
    folder.mkdir()
    set_folder_rule(folder, {"Images": [".jpg"]})
    set_folder_rule(folder, {"Images": [".png"], "Docs": [".pdf"]})
    entries = list_folder_rules()
    assert len(entries) == 1
    assert "Images" in entries[0]["rules"]
    assert "Docs" in entries[0]["rules"]
    assert entries[0]["rules"]["Images"] == [".png"]


def test_remove(fr_file, tmp_path):
    folder = tmp_path / "Downloads"
    folder.mkdir()
    set_folder_rule(folder, {"Images": [".jpg"]})
    remove_folder_rule(folder)
    assert get_folder_rule(folder) is None


def test_remove_unknown(fr_file):
    with pytest.raises(KeyError):
        remove_folder_rule("/nope/does/not/exist")


def test_normalises_extensions(fr_file, tmp_path):
    folder = tmp_path / "Downloads"
    folder.mkdir()
    set_folder_rule(folder, {"Images": ["jpg", ".PNG", " .gif "]})
    entry = get_folder_rule(folder)
    assert entry["rules"]["Images"] == [".gif", ".jpg", ".png"]


def test_path_matching_case_insensitive_windows(fr_file, tmp_path):
    folder = tmp_path / "Downloads"
    folder.mkdir()
    set_folder_rule(str(folder), {"Images": [".jpg"]})
    upper = str(folder).upper()
    entry = get_folder_rule(upper)
    assert entry is not None


def test_resolve_returns_global_when_no_match(fr_file, tmp_path):
    global_rules = [make_rule("Images", [".jpg"]), make_rule("Docs", [".pdf"])]
    folder = tmp_path / "Nowhere"
    folder.mkdir()
    resolved = resolve_rules_for(folder, global_rules)
    assert resolved == global_rules


def test_resolve_merges_and_overrides(fr_file, tmp_path):
    folder = tmp_path / "Downloads"
    folder.mkdir()
    set_folder_rule(folder, {"Images": [".heic"], "Installers": [".exe"]})

    global_rules = [
        make_rule("Images", [".jpg", ".png"]),
        make_rule("Docs", [".pdf"]),
    ]
    resolved = resolve_rules_for(folder, global_rules)
    by_name = {r.name: r.extensions for r in resolved}

    assert by_name["Images"] == {".heic"}
    assert by_name["Docs"] == {".pdf"}
    assert by_name["Installers"] == {".exe"}


def test_reset_clears_all(fr_file, tmp_path):
    folder = tmp_path / "Downloads"
    folder.mkdir()
    set_folder_rule(folder, {"Images": [".jpg"]})
    folder_rules.reset_all()
    assert list_folder_rules() == []
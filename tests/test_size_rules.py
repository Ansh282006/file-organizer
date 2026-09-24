"""Tests for size-based sub-bucketing within a category."""

import pytest

import organizer
from organizer import Rule, scan, set_size_split, load_rules


def make_file(folder, name, size_mb):
    p = folder / name
    with p.open("wb") as f:
        f.seek(int(size_mb * 1024 * 1024) - 1)
        f.write(b"\0")
    return p


@pytest.fixture
def rules_file(tmp_path, monkeypatch):
    rf = tmp_path / "rules.yaml"
    monkeypatch.setattr(organizer, "RULES_FILE", rf)
    return rf


def test_rule_without_size_split(rules_file):
    rules_file.write_text(
        "Documents:\n  extensions: [.pdf, .docx]\n",
        encoding="utf-8",
    )
    rules = load_rules()
    assert len(rules) == 1
    assert rules[0].size_split_mb is None


def test_rule_with_size_split(rules_file):
    rules_file.write_text(
        "Documents:\n  extensions: [.pdf]\n  size_split_mb: 10\n",
        encoding="utf-8",
    )
    rules = load_rules()
    assert rules[0].size_split_mb == 10.0


def test_invalid_size_split_ignored(rules_file):
    rules_file.write_text(
        "Documents:\n  extensions: [.pdf]\n  size_split_mb: 'garbage'\n",
        encoding="utf-8",
    )
    rules = load_rules()
    assert rules[0].size_split_mb is None


def test_scan_small_file_goes_to_small(rules_file, tmp_path):
    make_file(tmp_path, "tiny.pdf", 0.5)
    rules = [Rule(name="Documents", extensions={".pdf"}, size_split_mb=1.0)]
    plan = scan(tmp_path, rules=rules)
    assert plan.items[0].category == "Documents/small"


def test_scan_large_file_goes_to_large(rules_file, tmp_path):
    make_file(tmp_path, "big.pdf", 2.0)
    rules = [Rule(name="Documents", extensions={".pdf"}, size_split_mb=1.0)]
    plan = scan(tmp_path, rules=rules)
    assert plan.items[0].category == "Documents/large"


def test_scan_exactly_at_threshold_is_large(rules_file, tmp_path):
    make_file(tmp_path, "edge.pdf", 1.0)
    rules = [Rule(name="Documents", extensions={".pdf"}, size_split_mb=1.0)]
    plan = scan(tmp_path, rules=rules)
    assert plan.items[0].category == "Documents/large"


def test_scan_no_split_uses_flat_folder(rules_file, tmp_path):
    make_file(tmp_path, "file.pdf", 2.0)
    rules = [Rule(name="Documents", extensions={".pdf"}, size_split_mb=None)]
    plan = scan(tmp_path, rules=rules)
    assert plan.items[0].category == "Documents"


def test_already_sorted_in_split_subfolder(rules_file, tmp_path):
    sub = tmp_path / "Documents" / "large"
    sub.mkdir(parents=True)
    make_file(sub, "old.pdf", 5.0)
    rules = [Rule(name="Documents", extensions={".pdf"}, size_split_mb=1.0)]
    plan = scan(tmp_path, rules=rules)
    assert plan.total == 0
    assert len(plan.skipped) == 1


def test_set_size_split_persists(rules_file, tmp_path):
    rules_file.write_text(
        "Documents:\n  extensions: [.pdf]\n",
        encoding="utf-8",
    )
    set_size_split("Documents", 25.5)
    rules = load_rules()
    assert rules[0].size_split_mb == 25.5


def test_set_size_split_none_removes(rules_file):
    rules_file.write_text(
        "Documents:\n  extensions: [.pdf]\n  size_split_mb: 10\n",
        encoding="utf-8",
    )
    set_size_split("Documents", None)
    rules = load_rules()
    assert rules[0].size_split_mb is None


def test_set_size_split_invalid(rules_file):
    rules_file.write_text(
        "Documents:\n  extensions: [.pdf]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        set_size_split("Documents", 0)
    with pytest.raises(ValueError):
        set_size_split("Documents", -5)
    with pytest.raises(ValueError):
        set_size_split("Documents", "not a number")


def test_set_size_split_unknown_category(rules_file):
    rules_file.write_text("Documents:\n  extensions: [.pdf]\n", encoding="utf-8")
    with pytest.raises(KeyError):
        set_size_split("Nope", 10)
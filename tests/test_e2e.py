"""End-to-end integration tests.

These spin up the real FastAPI app in-process and exercise every endpoint
over a real HTTP (and WebSocket) transport. Config is isolated via
FO_DATA_DIR set in conftest.py — no real files are touched.
"""

from pathlib import Path


# ============================================================
# Health
# ============================================================

def test_health(app_client):
    r = app_client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "scheduler_running" in body
    assert "trash_supported" in body
    assert "ws_connections" in body


def test_unknown_endpoint_returns_404(app_client):
    r = app_client.get("/api/does-not-exist")
    assert r.status_code == 404


# ============================================================
# Scan
# ============================================================

def test_scan_missing_path_param(app_client):
    r = app_client.get("/api/scan")
    assert r.status_code == 422  # FastAPI query validation


def test_scan_bad_folder_returns_400(app_client):
    r = app_client.get("/api/scan", params={"path": "/nope/nope/nope"})
    assert r.status_code == 400


def test_scan_bad_mode_returns_400(app_client, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    r = app_client.get("/api/scan", params={"path": str(work), "mode": "banana"})
    assert r.status_code == 400


def test_scan_basic(app_client, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "a.jpg").write_text("x")
    (work / "b.pdf").write_text("y")
    (work / "c.py").write_text("z")

    r = app_client.get("/api/scan", params={"path": str(work), "mode": "extension"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["mode"] == "extension"
    cats = {it["category"] for it in body["items"]}
    assert cats == {"Images", "Documents", "Code"}


def test_scan_empty_folder(app_client, tmp_path):
    work = tmp_path / "empty"
    work.mkdir()
    r = app_client.get("/api/scan", params={"path": str(work)})
    assert r.status_code == 200
    assert r.json()["total"] == 0


# ============================================================
# Organize + Undo
# ============================================================

def test_organize_and_undo_full_cycle(app_client, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "photo.jpg").write_text("img")
    (work / "notes.txt").write_text("text")

    # --- Organize ---
    r = app_client.post("/api/organize", json={"path": str(work), "mode": "extension"})
    assert r.status_code == 200
    body = r.json()
    assert body["moved"] == 2
    log_file = body["log_file"]
    assert log_file and log_file.endswith(".json")

    # Files actually moved
    assert (work / "Images" / "photo.jpg").exists()
    assert (work / "Documents" / "notes.txt").exists()
    assert not (work / "photo.jpg").exists()

    # --- Logs ---
    r = app_client.get("/api/logs")
    logs = r.json()["logs"]
    entry = next(l for l in logs if l["file"] == log_file)
    assert entry["total"] == 2
    assert entry["undone"] is False
    assert entry["mode"] == "extension"

    # --- Undo ---
    r = app_client.post("/api/undo", json={"log_file": log_file})
    assert r.status_code == 200
    result = r.json()
    assert result["restored"] == 2
    assert result["errors"] == []

    # Files restored
    assert (work / "photo.jpg").exists()
    assert (work / "notes.txt").exists()
    assert not (work / "Images").exists()
    assert not (work / "Documents").exists()


def test_undo_same_log_twice_fails(app_client, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "a.jpg").write_text("x")

    r = app_client.post("/api/organize", json={"path": str(work), "mode": "extension"})
    log_file = r.json()["log_file"]

    r = app_client.post("/api/undo", json={"log_file": log_file})
    assert r.status_code == 200

    r = app_client.post("/api/undo", json={"log_file": log_file})
    assert r.status_code == 400


def test_undo_no_undoable_log_returns_404(app_client):
    r = app_client.post("/api/undo", json={})
    assert r.status_code == 404


def test_organize_missing_path_returns_400(app_client):
    r = app_client.post("/api/organize", json={})
    assert r.status_code == 400


def test_organize_empty_folder(app_client, tmp_path):
    work = tmp_path / "empty"
    work.mkdir()
    r = app_client.post("/api/organize", json={"path": str(work)})
    assert r.status_code == 200
    assert r.json()["moved"] == 0


# ============================================================
# Rules CRUD
# ============================================================

def test_rules_list(app_client):
    r = app_client.get("/api/rules")
    assert r.status_code == 200
    rules = r.json()
    assert isinstance(rules, dict)
    assert "Images" in rules


def test_rules_add_and_remove_extension(app_client):
    r = app_client.post("/api/rules/add-extension",
                        json={"category": "Images", "extension": ".heif"})
    assert r.status_code == 200
    rules = app_client.get("/api/rules").json()
    assert ".heif" in rules["Images"]

    r = app_client.post("/api/rules/remove-extension",
                        json={"category": "Images", "extension": ".heif"})
    assert r.status_code == 200
    rules = app_client.get("/api/rules").json()
    assert ".heif" not in rules["Images"]


def test_rules_add_extension_unknown_category_404(app_client):
    r = app_client.post("/api/rules/add-extension",
                        json={"category": "Nope", "extension": ".xyz"})
    assert r.status_code == 404


def test_rules_add_and_remove_category(app_client):
    r = app_client.post("/api/rules/add-category",
                        json={"name": "Videos", "extensions": [".mp4", ".mkv"]})
    assert r.status_code == 200
    rules = app_client.get("/api/rules").json()
    assert "Videos" in rules
    assert set(rules["Videos"]) == {".mp4", ".mkv"}

    r = app_client.post("/api/rules/remove-category", json={"name": "Videos"})
    assert r.status_code == 200
    rules = app_client.get("/api/rules").json()
    assert "Videos" not in rules


def test_rules_add_duplicate_category_400(app_client):
    r = app_client.post("/api/rules/add-category", json={"name": "Images"})
    assert r.status_code == 400


# ============================================================
# Settings
# ============================================================

def test_settings_get(app_client):
    r = app_client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert "settings" in body
    assert "date_format_options" in body
    assert body["settings"]["default_mode"] == "extension"


def test_settings_update_default_mode(app_client):
    r = app_client.post("/api/settings", json={"default_mode": "date"})
    assert r.status_code == 200
    assert r.json()["settings"]["default_mode"] == "date"

    # Persists across requests
    r = app_client.get("/api/settings")
    assert r.json()["settings"]["default_mode"] == "date"

    # Revert for other tests
    app_client.post("/api/settings", json={"default_mode": "extension"})


def test_settings_invalid_mode_400(app_client):
    r = app_client.post("/api/settings", json={"default_mode": "banana"})
    assert r.status_code == 400


def test_settings_skip_names_must_be_list(app_client):
    r = app_client.post("/api/settings", json={"skip_names": "not a list"})
    assert r.status_code == 400


# ============================================================
# Folder rules
# ============================================================

def test_folder_rules_crud(app_client, tmp_path):
    work = tmp_path / "dl"
    work.mkdir()

    # Initially empty
    r = app_client.get("/api/folder-rules")
    assert r.status_code == 200
    assert r.json()["folders"] == []

    # Add
    r = app_client.post("/api/folder-rules", json={
        "path": str(work),
        "rules": {"Installers": [".exe", ".msi"]},
    })
    assert r.status_code == 200
    entry = r.json()["entry"]
    assert entry["rules"]["Installers"] == [".exe", ".msi"]

    # List
    r = app_client.get("/api/folder-rules")
    folders = r.json()["folders"]
    assert len(folders) == 1
    assert folders[0]["path"] == str(work.resolve())

    # Resolve (merged with global)
    r = app_client.get("/api/folder-rules/resolve", params={"path": str(work)})
    assert r.status_code == 200
    eff = r.json()["effective_rules"]
    assert "Installers" in eff          # from folder
    assert "Images" in eff              # from global
    assert set(eff["Installers"]) == {".exe", ".msi"}

    # Delete
    r = app_client.delete("/api/folder-rules", params={"path": str(work)})
    assert r.status_code == 200
    assert app_client.get("/api/folder-rules").json()["folders"] == []


def test_folder_rules_delete_unknown_404(app_client):
    r = app_client.delete("/api/folder-rules", params={"path": "/nope/nope"})
    assert r.status_code == 404


def test_folder_rules_override_applies_to_scan(app_client, tmp_path):
    work = tmp_path / "dl"
    work.mkdir()
    (work / "installer.custominstall").write_text("x")
    (work / "photo.jpg").write_text("y")

    # Global rules don't have .custominstall → falls into Misc
    r = app_client.get("/api/scan", params={"path": str(work)})
    assert r.status_code == 200
    cats = {it["source_name"]: it["category"] for it in r.json()["items"]}
    assert cats["installer.custominstall"] == "Misc"

    # Add folder rule for .custominstall → Custom
    app_client.post("/api/folder-rules", json={
        "path": str(work),
        "rules": {"Custom": [".custominstall"]},
    })

    # Scan again — now .custominstall goes to Custom
    r = app_client.get("/api/scan", params={"path": str(work)})
    assert r.status_code == 200
    cats = {it["source_name"]: it["category"] for it in r.json()["items"]}
    assert cats["installer.custominstall"] == "Custom"
    assert cats["photo.jpg"] == "Images"


# ============================================================
# Schedules
# ============================================================

def test_schedules_crud(app_client, tmp_path):
    work = tmp_path / "work"
    work.mkdir()

    r = app_client.get("/api/schedules")
    assert r.status_code == 200
    assert r.json()["schedules"] == []
    assert "scheduler_running" in r.json()

    # Add
    r = app_client.post("/api/schedules", json={
        "folder": str(work),
        "mode": "extension",
        "interval_minutes": 60,
    })
    assert r.status_code == 200
    sid = r.json()["schedule"]["id"]

    r = app_client.get("/api/schedules")
    assert len(r.json()["schedules"]) == 1

    # Disable
    r = app_client.post(f"/api/schedules/{sid}", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["schedule"]["enabled"] is False

    # Run now
    r = app_client.post(f"/api/schedules/{sid}/run")
    assert r.status_code == 200
    assert "last_moved" in r.json()["schedule"]

    # Delete
    r = app_client.delete(f"/api/schedules/{sid}")
    assert r.status_code == 200
    assert app_client.get("/api/schedules").json()["schedules"] == []


def test_schedules_invalid_folder_400(app_client):
    r = app_client.post("/api/schedules", json={"folder": "/nope/nope"})
    assert r.status_code == 400


def test_schedules_unknown_id_404(app_client):
    r = app_client.delete("/api/schedules/nonexistent")
    assert r.status_code == 404


# ============================================================
# Duplicates
# ============================================================

def test_duplicates_find(app_client, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "a.txt").write_text("same")
    (work / "b.txt").write_text("same")
    (work / "c.txt").write_text("unique")

    r = app_client.get("/api/duplicates", params={"path": str(work)})
    assert r.status_code == 200
    body = r.json()
    assert body["total_groups"] == 1
    assert body["total_files"] == 3
    assert body["wasted_bytes"] == 4
    assert len(body["groups"][0]["files"]) == 2


def test_duplicates_quarantine(app_client, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "a.txt").write_text("same")
    (work / "b.txt").write_text("same")

    r = app_client.post("/api/duplicates/quarantine", json={"path": str(work)})
    assert r.status_code == 200
    body = r.json()
    assert body["moved"] == 1
    assert (work / "_duplicates").is_dir()
    assert len(list((work / "_duplicates").iterdir())) == 1


def test_duplicates_no_matches(app_client, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "a.txt").write_text("unique1")
    (work / "b.txt").write_text("unique2")

    r = app_client.get("/api/duplicates", params={"path": str(work)})
    assert r.json()["total_groups"] == 0


# ============================================================
# Large files
# ============================================================

def test_large_files_find(app_client, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    with (work / "big.bin").open("wb") as f:
        f.seek(2 * 1024 * 1024 - 1)
        f.write(b"\0")
    (work / "small.bin").write_text("small")

    r = app_client.get("/api/large-files", params={"path": str(work), "min_mb": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["matched"] == 1
    assert body["files"][0]["name"] == "big.bin"
    assert body["files"][0]["size"] >= 2 * 1024 * 1024 - 1


def test_large_files_nothing_matches(app_client, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "small.bin").write_text("x")

    r = app_client.get("/api/large-files", params={"path": str(work), "min_mb": 100})
    assert r.status_code == 200
    assert r.json()["matched"] == 0


def test_large_files_quarantine(app_client, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    with (work / "big.bin").open("wb") as f:
        f.seek(2 * 1024 * 1024 - 1)
        f.write(b"\0")

    files = app_client.get("/api/large-files", params={"path": str(work), "min_mb": 1}).json()["files"]
    r = app_client.post("/api/large-files/quarantine",
                        json={"path": str(work), "files": files})
    assert r.status_code == 200
    assert r.json()["moved"] == 1
    assert (work / "_large_files" / "big.bin").exists()
    assert not (work / "big.bin").exists()


# ============================================================
# Config export / import / reset
# ============================================================

def test_config_export_shape(app_client):
    r = app_client.get("/api/config/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    for key in ("version", "exported_at", "rules", "settings", "schedules", "folder_rules"):
        assert key in body


def test_config_import_replace(app_client):
    bundle = {
        "version": 1,
        "rules": {"Videos": {"extensions": [".mp4"]}},
        "settings": {
            "default_mode": "extension",
            "date_format": "%Y-%m",
            "skip_names": [],
            "skip_prefixes": [],
        },
        "schedules": {"schedules": []},
        "folder_rules": {"folders": []},
    }
    r = app_client.post("/api/config/import",
                        json={"bundle": bundle, "strategy": "replace"})
    assert r.status_code == 200
    applied = r.json()["applied"]
    assert applied["rules"] >= 1

    rules = app_client.get("/api/rules").json()
    assert "Videos" in rules
    assert "Images" not in rules  # replaced


def test_config_import_merge(app_client):
    # Ensure we start with something
    app_client.post("/api/rules/add-category", json={"name": "Keep", "extensions": [".keep"]})

    bundle = {
        "version": 1,
        "rules": {"Merged": {"extensions": [".m"]}},
        "settings": {},
        "schedules": {"schedules": []},
        "folder_rules": {"folders": []},
    }
    r = app_client.post("/api/config/import",
                        json={"bundle": bundle, "strategy": "merge"})
    assert r.status_code == 200

    rules = app_client.get("/api/rules").json()
    assert "Keep" in rules
    assert "Merged" in rules


def test_config_import_invalid_strategy_400(app_client):
    r = app_client.post("/api/config/import",
                        json={"bundle": {}, "strategy": "banana"})
    assert r.status_code == 400


def test_config_import_missing_bundle_400(app_client):
    r = app_client.post("/api/config/import", json={})
    assert r.status_code == 400


def test_config_reset_restores_defaults(app_client):
    # Change a bunch of things
    app_client.post("/api/settings", json={"default_mode": "date"})
    app_client.post("/api/rules/add-category", json={"name": "TestCat"})

    r = app_client.post("/api/config/reset")
    assert r.status_code == 200

    settings = app_client.get("/api/settings").json()["settings"]
    assert settings["default_mode"] == "extension"

    rules = app_client.get("/api/rules").json()
    assert "Images" in rules
    assert "TestCat" not in rules


# ============================================================
# WebSocket
# ============================================================

def test_ws_hello(app_client):
    with app_client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "hello"
        assert "connections" in msg["data"]
        assert msg["data"]["connections"] >= 1


def test_ws_connection_reflected_in_health(app_client):
    with app_client.websocket_connect("/ws") as ws:
        ws.receive_json()  # consume hello

        r = app_client.get("/api/health")
        assert r.json()["ws_connections"] >= 1


# ============================================================
# End-to-end flow: rules change → scan uses new rule
# ============================================================

def test_e2e_add_rule_then_scan_uses_it(app_client, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "file.xyz").write_text("x")

    # Before: .xyz has no rule → Misc
    r = app_client.get("/api/scan", params={"path": str(work)})
    assert r.json()["items"][0]["category"] == "Misc"

    # Add a rule
    app_client.post("/api/rules/add-category", json={"name": "Weird", "extensions": [".xyz"]})

    # After: .xyz → Weird
    r = app_client.get("/api/scan", params={"path": str(work)})
    assert r.json()["items"][0]["category"] == "Weird"
"""File Organizer — FastAPI backend."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, WebSocket
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

import events
import folder_rules as fr
from config_io import export_bundle, import_bundle, reset_all
from duplicates import find_duplicates, plan_quarantine
from organizer import (
    MODE_EXTENSION,
    VALID_MODES,
    add_category,
    add_extension,
    execute,
    latest_undoable_log,
    list_logs,
    load_rules,
    remove_category,
    remove_extension,
    scan,
    undo,
    Plan,
)
from scheduler import (
    SchedulerService,
    add_schedule,
    list_schedules,
    remove_schedule,
    run_schedule_now,
    update_schedule,
)
from settings import DATE_FORMAT_OPTIONS, load_settings, update_settings
from thumbnails import generate_thumbnail, is_image
from trash import is_supported as trash_supported, trash_many
from watcher import WatchManager

app = FastAPI(title="File Organizer", version="1.0.0")

STATIC_DIR = Path(__file__).parent / "static"
watch_manager = WatchManager()
scheduler_service = SchedulerService()

_broadcast_task: asyncio.Task | None = None


@app.on_event("startup")
async def _startup():
    global _broadcast_task
    _broadcast_task = asyncio.create_task(events.broadcast_loop())
    scheduler_service.start()


@app.on_event("shutdown")
async def _shutdown():
    scheduler_service.stop()
    if _broadcast_task:
        _broadcast_task.cancel()


def _resolved_rules(path: str | Path) -> list:
    """Global rules merged with folder-specific rules (if any)."""
    return fr.resolve_rules_for(path, load_rules())


def _scan_with_settings(path: str, mode: str | None = None) -> Plan:
    s = load_settings()
    effective_mode = mode or s.default_mode
    return scan(
        Path(path),
        rules=_resolved_rules(path),
        mode=effective_mode,
        date_format=s.date_format,
        skip_names=set(s.skip_names),
        skip_prefixes=tuple(s.skip_prefixes),
    )


# ---------- WebSocket ----------

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await events.handle_connection(websocket)


# ---------- API ----------

@app.get("/api/health")
def api_health():
    return {
        "status": "ok",
        "scheduler_running": scheduler_service.running,
        "trash_supported": trash_supported(),
        "ws_connections": events.connection_count(),
    }


@app.get("/api/scan")
def api_scan(path: str = Query(...), mode: str | None = Query(None)):
    if mode is not None and mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
    try:
        plan = _scan_with_settings(path, mode)
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"Permission denied: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
    return plan_to_json(plan)


@app.get("/api/thumbnail")
def api_thumbnail(path: str = Query(...)):
    p = Path(path)
    if not is_image(p):
        raise HTTPException(status_code=400, detail="Not a supported image")
    try:
        data = generate_thumbnail(p)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.post("/api/organize")
def api_organize(payload: dict):
    path = payload.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="Missing 'path' in request body")
    mode = payload.get("mode")
    if mode is not None and mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
    try:
        plan = _scan_with_settings(path, mode)
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"Permission denied: {e}")

    if plan.total == 0:
        return {"moved": 0, "errors": [], "log_file": None, "message": "Nothing to organize"}
    log_path = execute(plan)
    events.publish("organize", {
        "folder": str(plan.folder),
        "moved": plan.total,
        "mode": plan.mode,
        "log": log_path.name,
    })
    return {
        "moved": plan.total,
        "renamed": plan.renamed,
        "mode": plan.mode,
        "errors": [],
        "log_file": log_path.name,
        "message": f"Moved {plan.total} file(s)",
    }


@app.get("/api/logs")
def api_logs():
    return {"logs": list_logs()}


@app.post("/api/undo")
def api_undo(payload: dict | None = None):
    log_name = (payload or {}).get("log_file")
    if log_name:
        log_path = Path(__file__).parent / "logs" / log_name
    else:
        log_path = latest_undoable_log()
    if not log_path:
        raise HTTPException(status_code=404, detail="No undoable log found")
    try:
        result = undo(log_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
    events.publish("undo", {
        "log": result.get("log_file"),
        "restored": result.get("restored", 0),
    })
    return result


# ---------- trash ----------

@app.get("/api/trash/status")
def api_trash_status():
    return {"supported": trash_supported()}


@app.post("/api/trash")
def api_trash(payload: dict):
    if not trash_supported():
        raise HTTPException(status_code=501, detail="OS trash not available")
    paths = payload.get("paths")
    if not isinstance(paths, list) or not paths:
        raise HTTPException(status_code=400, detail="Missing 'paths' list")
    result = trash_many([Path(p) for p in paths])
    events.publish("trash", {"trashed": result["trashed"], "failed": result["failed"]})
    return result


# ---------- config bundle ----------

@app.get("/api/config/export")
def api_config_export():
    bundle = export_bundle()
    body = json.dumps(bundle, indent=2)
    ts = bundle["exported_at"].replace(":", "").replace(" ", "_").replace("-", "")
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="file-organizer-config-{ts}.json"'},
    )


@app.post("/api/config/import")
def api_config_import(payload: dict):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    bundle = payload.get("bundle")
    strategy = payload.get("strategy", "replace")
    if not isinstance(bundle, dict):
        raise HTTPException(status_code=400, detail="Missing 'bundle' in request body")
    try:
        applied = import_bundle(bundle, strategy=strategy)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    events.publish("config_imported", {"applied": applied})
    return {"ok": True, "applied": applied}


@app.post("/api/config/reset")
def api_config_reset():
    reset_all()
    events.publish("config_reset", {})
    return {"ok": True}


# ---------- duplicates ----------

@app.get("/api/duplicates")
def api_duplicates(path: str = Query(...)):
    s = load_settings()
    try:
        return find_duplicates(Path(path), skip_names=set(s.skip_names), skip_prefixes=tuple(s.skip_prefixes))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"Permission denied: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/duplicates/quarantine")
def api_duplicates_quarantine(payload: dict):
    path = payload.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="Missing 'path' in request body")
    s = load_settings()
    try:
        result = find_duplicates(Path(path), skip_names=set(s.skip_names), skip_prefixes=tuple(s.skip_prefixes))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
    if result["total_groups"] == 0:
        return {"moved": 0, "log_file": None, "message": "No duplicates found"}
    plan = plan_quarantine(Path(path), result["groups"])
    if plan.total == 0:
        return {"moved": 0, "log_file": None, "message": "Nothing to quarantine"}
    log_path = execute(plan)
    events.publish("quarantine", {
        "folder": str(plan.folder),
        "moved": plan.total,
        "log": log_path.name,
    })
    return {
        "moved": plan.total,
        "log_file": log_path.name,
        "message": f"Quarantined {plan.total} duplicate(s) into _duplicates/",
    }


@app.post("/api/duplicates/trash")
def api_duplicates_trash(payload: dict):
    if not trash_supported():
        raise HTTPException(status_code=501, detail="OS trash not available")
    path = payload.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="Missing 'path' in request body")
    s = load_settings()
    try:
        result = find_duplicates(Path(path), skip_names=set(s.skip_names), skip_prefixes=tuple(s.skip_prefixes))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    if result["total_groups"] == 0:
        return {"trashed": 0, "failed": 0, "message": "No duplicates found"}

    to_trash: list[Path] = []
    for group in result["groups"]:
        for f in group["files"][1:]:
            to_trash.append(Path(f["path"]))

    if not to_trash:
        return {"trashed": 0, "failed": 0, "message": "Nothing to trash"}

    trash_result = trash_many(to_trash)
    trash_result["message"] = (
        f"Sent {trash_result['trashed']} duplicate(s) to OS trash"
        + (f" ({trash_result['failed']} failed)" if trash_result.get("failed") else "")
    )
    events.publish("trash", {"trashed": trash_result["trashed"], "failed": trash_result["failed"]})
    return trash_result


# ---------- folder rules ----------

@app.get("/api/folder-rules")
def api_list_folder_rules():
    return {"folders": fr.list_folder_rules()}


@app.post("/api/folder-rules")
def api_set_folder_rule(payload: dict):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    path = payload.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="Missing 'path'")
    rules = payload.get("rules")
    if rules is None:
        rules = {}
    if not isinstance(rules, dict):
        raise HTTPException(status_code=400, detail="'rules' must be an object")

    for name, exts in rules.items():
        if not isinstance(exts, list):
            raise HTTPException(status_code=400, detail=f"Extensions for '{name}' must be a list")

    try:
        entry = fr.set_folder_rule(path, rules)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    events.publish("folder_rules_updated", {"path": entry["path"]})
    return {"ok": True, "entry": entry}


@app.delete("/api/folder-rules")
def api_delete_folder_rule(path: str = Query(...)):
    try:
        fr.remove_folder_rule(path)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    events.publish("folder_rules_updated", {"path": path})
    return {"ok": True}


@app.get("/api/folder-rules/resolve")
def api_resolve_folder_rules(path: str = Query(...)):
    resolved = _resolved_rules(path)
    return {
        "folder": path,
        "effective_rules": {r.name: sorted(r.extensions) for r in resolved},
    }


# ---------- schedules ----------

@app.get("/api/schedules")
def api_list_schedules():
    return {
        "schedules": list_schedules(),
        "scheduler_running": scheduler_service.running,
    }


@app.post("/api/schedules")
def api_add_schedule(payload: dict):
    folder = payload.get("folder")
    if not folder:
        raise HTTPException(status_code=400, detail="Missing 'folder'")
    mode = payload.get("mode", MODE_EXTENSION)
    interval = payload.get("interval_minutes", 60)
    try:
        entry = add_schedule(folder, mode=mode, interval_minutes=int(interval))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "schedule": entry}


@app.post("/api/schedules/{schedule_id}")
def api_update_schedule(schedule_id: str, payload: dict):
    try:
        updated = update_schedule(schedule_id, payload)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "schedule": updated}


@app.delete("/api/schedules/{schedule_id}")
def api_delete_schedule(schedule_id: str):
    try:
        remove_schedule(schedule_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


@app.post("/api/schedules/{schedule_id}/run")
def api_run_schedule(schedule_id: str):
    try:
        result = run_schedule_now(schedule_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "schedule": result}


# ---------- settings ----------

@app.get("/api/settings")
def api_get_settings():
    s = load_settings()
    return {"settings": s.to_dict(), "date_format_options": DATE_FORMAT_OPTIONS}


@app.post("/api/settings")
def api_update_settings(payload: dict):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    try:
        updated = update_settings(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    events.publish("settings_updated", {"settings": updated.to_dict()})
    return {"ok": True, "settings": updated.to_dict()}


# ---------- watch ----------

@app.get("/api/watch/status")
def api_watch_status():
    return watch_manager.status()


@app.post("/api/watch/start")
def api_watch_start(payload: dict):
    path = payload.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="Missing 'path'")
    mode = payload.get("mode") or load_settings().default_mode
    try:
        return watch_manager.start(Path(path), mode=mode)
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/watch/stop")
def api_watch_stop():
    return watch_manager.stop()


# ---------- rules (global) ----------

@app.get("/api/rules")
def api_rules():
    rules = load_rules()
    return {r.name: sorted(r.extensions) for r in rules}


@app.post("/api/rules/add-extension")
def api_add_extension(payload: dict):
    category = payload.get("category")
    extension = payload.get("extension")
    if not category or not extension:
        raise HTTPException(status_code=400, detail="Missing category or extension")
    try:
        add_extension(category, extension)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    events.publish("rules_updated", {})
    return {"ok": True}


@app.post("/api/rules/remove-extension")
def api_remove_extension(payload: dict):
    category = payload.get("category")
    extension = payload.get("extension")
    if not category or not extension:
        raise HTTPException(status_code=400, detail="Missing category or extension")
    try:
        remove_extension(category, extension)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    events.publish("rules_updated", {})
    return {"ok": True}


@app.post("/api/rules/add-category")
def api_add_category(payload: dict):
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Missing category name")
    try:
        add_category(name, payload.get("extensions") or [])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    events.publish("rules_updated", {})
    return {"ok": True}


@app.post("/api/rules/remove-category")
def api_remove_category(payload: dict):
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Missing category name")
    try:
        remove_category(name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    events.publish("rules_updated", {})
    return {"ok": True}


def plan_to_json(plan: Plan) -> dict:
    return {
        "folder": str(plan.folder),
        "mode": plan.mode,
        "total": plan.total,
        "renamed": plan.renamed,
        "skipped": [str(p) for p in plan.skipped],
        "items": [
            {
                "source": str(it.source),
                "source_name": it.source.name,
                "destination": str(it.destination),
                "destination_rel": str(it.destination.relative_to(plan.folder)),
                "category": it.category,
                "renamed": it.renamed,
                "is_image": is_image(it.source),
            }
            for it in plan.items
        ],
    }


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
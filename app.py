"""File Organizer — FastAPI backend."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

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
from watcher import WatchManager

app = FastAPI(title="File Organizer", version="0.7.0")

STATIC_DIR = Path(__file__).parent / "static"
watch_manager = WatchManager()
scheduler_service = SchedulerService()


@app.on_event("startup")
def _start_scheduler():
    scheduler_service.start()


@app.on_event("shutdown")
def _stop_scheduler():
    scheduler_service.stop()


def _scan_with_settings(path: str, mode: str | None = None) -> Plan:
    s = load_settings()
    effective_mode = mode or s.default_mode
    return scan(
        Path(path),
        mode=effective_mode,
        date_format=s.date_format,
        skip_names=set(s.skip_names),
        skip_prefixes=tuple(s.skip_prefixes),
    )


# ---------- API ----------

@app.get("/api/health")
def api_health():
    return {"status": "ok", "scheduler_running": scheduler_service.running}


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
    return result


# ---------- config bundle ----------

@app.get("/api/config/export")
def api_config_export():
    """Download the config bundle as a JSON file."""
    bundle = export_bundle()
    import json
    body = json.dumps(bundle, indent=2)
    filename = f"file-organizer-config-{bundle['exported_at'].replace(':', '').replace(' ', '_').replace('-', '')}.json"
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
    return {"ok": True, "applied": applied}


@app.post("/api/config/reset")
def api_config_reset():
    reset_all()
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
    return {
        "moved": plan.total,
        "log_file": log_path.name,
        "message": f"Quarantined {plan.total} duplicate(s) into _duplicates/",
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


# ---------- rules ----------

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
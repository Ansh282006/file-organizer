"""File Organizer — FastAPI backend."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

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
from watcher import WatchManager

app = FastAPI(title="File Organizer", version="0.2.0")

STATIC_DIR = Path(__file__).parent / "static"
watch_manager = WatchManager()


# ---------- API ----------

@app.get("/api/health")
def api_health():
    return {"status": "ok"}


@app.get("/api/scan")
def api_scan(
    path: str = Query(..., description="Absolute or ~-relative folder path"),
    mode: str = Query(MODE_EXTENSION, description="'extension' or 'date'"),
):
    if mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")

    try:
        plan = scan(Path(path), mode=mode)
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"Permission denied: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    return plan_to_json(plan)


@app.post("/api/organize")
def api_organize(payload: dict):
    path = payload.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="Missing 'path' in request body")

    mode = payload.get("mode", MODE_EXTENSION)
    if mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")

    try:
        plan = scan(Path(path), mode=mode)
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"Permission denied: {e}")

    if plan.total == 0:
        return {
            "moved": 0,
            "errors": [],
            "log_file": None,
            "message": "Nothing to organize",
        }

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


# ---------- watch endpoints ----------

@app.get("/api/watch/status")
def api_watch_status():
    return watch_manager.status()


@app.post("/api/watch/start")
def api_watch_start(payload: dict):
    path = payload.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="Missing 'path'")
    mode = payload.get("mode", MODE_EXTENSION)
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


# ---------- rules endpoints ----------

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
            }
            for it in plan.items
        ],
    }


# ---------- static frontend ----------

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
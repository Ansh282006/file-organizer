"""File Organizer — FastAPI backend."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from organizer import load_rules, scan, Plan

app = FastAPI(title="File Organizer", version="0.1.0")

STATIC_DIR = Path(__file__).parent / "static"


# ---------- API ----------

@app.get("/api/scan")
def api_scan(path: str = Query(..., description="Absolute or ~-relative folder path")):
    """
    Scan a folder and return the plan as JSON.
    Does NOT move any files — this is read-only.
    """
    try:
        plan = scan(Path(path))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"Permission denied: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    return plan_to_json(plan)


@app.get("/api/rules")
def api_rules():
    """Return the current rules.yaml as JSON so the UI can display it."""
    rules = load_rules()
    return {r.name: sorted(r.extensions) for r in rules}


@app.get("/api/health")
def api_health():
    return {"status": "ok"}


def plan_to_json(plan: Plan) -> dict:
    """Serialise a Plan object for the frontend."""
    return {
        "folder": str(plan.folder),
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


# ---------- static frontend (added in Step 5) ----------

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
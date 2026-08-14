"""
Financial Auditor — FastAPI Backend
Run: python server.py  →  http://localhost:8000
"""
import json
import uuid
import threading
import time
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import asyncio

from config.settings import UPLOADS_DIR
from agents.workflow import AuditWorkflowPipeline
from mcp_tools.db_handler import get_all_records, get_record_count, clear_all_records, init_db
from mcp_tools.server import export_audit_excel_tool

# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="Financial Auditor API", version="2.0.0")
init_db()

# In-memory job store: job_id → {status, events, result}
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


# ── Background Audit Runner ───────────────────────────────────────────────────
def _run_pipeline(job_id: str, file_name: str, file_path: str) -> None:
    """Runs the 4-agent pipeline in a daemon thread, emitting SSE events."""

    def emit(pct: int, msg: str) -> None:
        with _lock:
            _jobs[job_id]["events"].append(
                {"type": "progress", "pct": pct, "msg": msg}
            )

    try:
        with _lock:
            _jobs[job_id]["status"] = "running"

        pipeline = AuditWorkflowPipeline()
        results = pipeline.run_pipeline(
            file_name=file_name,
            file_path=file_path,
            progress_callback=emit,
        )

        with _lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["result"] = results
            _jobs[job_id]["events"].append(
                {"type": "done", "results": _serialisable(results)}
            )

    except Exception as exc:
        with _lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["events"].append(
                {"type": "error", "msg": str(exc)}
            )


def _serialisable(obj):
    """Recursively make an object JSON-safe."""
    if isinstance(obj, dict):
        return {k: _serialisable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialisable(i) for i in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


# ── API Routes ────────────────────────────────────────────────────────────────
@app.post("/api/audit")
async def start_audit(file: UploadFile = File(...)):
    """Upload a document and kick off the audit pipeline."""
    job_id = str(uuid.uuid4())
    save_path = UPLOADS_DIR / file.filename

    # Persist file
    content = await file.read()
    with open(save_path, "wb") as fh:
        fh.write(content)

    # Register job
    with _lock:
        _jobs[job_id] = {
            "status": "queued",
            "file_name": file.filename,
            "events": [],
            "result": None,
            "created_at": datetime.now().isoformat(),
        }

    # Launch pipeline thread
    threading.Thread(
        target=_run_pipeline,
        args=(job_id, file.filename, str(save_path)),
        daemon=True,
    ).start()

    return {"job_id": job_id, "file_name": file.filename}


@app.get("/api/audit/{job_id}/stream")
async def stream_audit(job_id: str):
    """SSE endpoint — streams progress events until job is done."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def generator():
        sent = 0
        # Send keep-alive comment immediately so browser doesn't wait
        yield ": keep-alive\n\n"
        while True:
            with _lock:
                job = _jobs.get(job_id, {})
                events = job.get("events", [])
                status = job.get("status", "queued")

            # Drain pending events
            while sent < len(events):
                yield f"data: {json.dumps(events[sent], ensure_ascii=False)}\n\n"
                sent += 1

            if status in ("done", "error"):
                break

            # Heartbeat every 3 s so browser keeps connection alive
            yield ": heartbeat\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/history")
async def get_history():
    """Return all audit records + aggregate counts."""
    return {"records": get_all_records(), "counts": get_record_count()}


@app.delete("/api/history")
async def delete_history():
    """Clear all audit records from the database."""
    clear_all_records()
    return {"success": True, "message": "All audit records deleted successfully."}


@app.post("/api/export")
async def export_excel():
    """Export full audit history to .xlsx and return as file download."""
    result = export_audit_excel_tool()
    if result.get("success"):
        return FileResponse(
            path=result["file_path"],
            filename=result["file_name"],
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
    raise HTTPException(status_code=400, detail=result["message"])


@app.get("/api/models")
async def check_models():
    """Ping LLM server and verify all configured models are present."""
    from config.settings import get_llm_client, MODELS, LLM_API_BASE
    try:
        client = get_llm_client()
        available = [m.id for m in client.models.list().data]
        return {
            "endpoint": LLM_API_BASE,
            "available": available,
            "configured": MODELS,
            "all_ready": all(v in available for v in MODELS.values()),
        }
    except Exception as exc:
        return {"error": str(exc)}


# ── Static Files & Root ────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)

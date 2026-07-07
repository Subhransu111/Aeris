import sys
import os
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uuid

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (REPO_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from .models import ScanRequest, ScanStatusResponse
    from .scan_runner import run_full_scan, SCAN_STATUS
except ImportError:  # pragma: no cover - fallback for direct module execution
    from models import ScanRequest, ScanStatusResponse
    from scan_runner import run_full_scan, SCAN_STATUS

app = FastAPI(title="Aegis AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production to your actual frontend origin
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/scan")
def start_scan(request: ScanRequest):
    scan_id = str(uuid.uuid4())
    SCAN_STATUS[scan_id] = {"status": "queued", "current_step": "accepted", "error": None}

    reg_config = request.registration_config.dict() if request.registration_config else None

    thread = threading.Thread(
        target=run_full_scan,
        args=(scan_id, request.repo_url, request.app_name,
              request.frontend_subdirectory, request.backend_subdirectory,
              request.tier, reg_config),
        daemon=True,
    )
    thread.start()
    return {"scan_id": scan_id, "status": "queued"}


@app.get("/api/scan/{scan_id}/status")
def get_scan_status(scan_id: str):
    return SCAN_STATUS.get(scan_id, {"status": "not_found"})


@app.get("/api/scan/{scan_id}/report")
def get_scan_report(scan_id: str):
    result = SCAN_STATUS.get(scan_id)
    if not result or result.get("status") != "completed":
        return {"error": "Report not ready or scan not found"}
    return {"report": result["report_json"], "markdown": result["report_markdown"]}
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import threading
import uuid

from server.scan_runner import run_full_scan, SCAN_STATUS
from core.evidence.evidence_store import get_run_evidence

app = FastAPI(title="Aegis AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/screenshots", StaticFiles(directory="screenshots"), name="screenshots")


# ---------- Models ----------

class RegistrationField(BaseModel):
    selector_hint: str
    type: str
    value: str

class RegistrationStep(BaseModel):
    step_name: str
    fields: List[RegistrationField]

class RegistrationConfig(BaseModel):
    signup_url: str
    fields: List[RegistrationField]
    additional_steps: Optional[List[RegistrationStep]] = []
    submit_button_text: Optional[str] = None
    login_url: str
    login_identifier_value: str
    login_password_value: str

class ScanRequest(BaseModel):
    repo_url: str
    app_name: str
    frontend_subdirectory: Optional[str] = None
    backend_subdirectory: Optional[str] = None
    tier: str = "free"
    registration_config: Optional[RegistrationConfig] = None


# ---------- Single scan pipeline ----------

@app.post("/api/scan")
def start_scan(request: ScanRequest):
    scan_id = str(uuid.uuid4())
    SCAN_STATUS[scan_id] = {"status": "queued"}

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


# ---------- Status / results retrieval ----------

@app.get("/api/scan/{scan_id}/status")
def get_scan_status(scan_id: str):
    return SCAN_STATUS.get(scan_id, {"status": "not_found"})


@app.get("/api/scan/{scan_id}/sitemap")
def get_scan_sitemap(scan_id: str):
    result = SCAN_STATUS.get(scan_id)
    if not result or "sitemap" not in result:
        return {"error": "Sitemap not available yet"}
    return result["sitemap"]


@app.get("/api/scan/{scan_id}/evidence")
def get_all_scan_evidence(scan_id: str):
    result = SCAN_STATUS.get(scan_id)
    if not result or "run_id" not in result:
        return {"error": "Run not found or not completed"}
    return {"records": get_run_evidence(result["run_id"])}


@app.get("/api/scan/{scan_id}/evidence/{agent_type}")
def get_scan_evidence_by_agent(scan_id: str, agent_type: str):
    result = SCAN_STATUS.get(scan_id)
    if not result or "run_id" not in result:
        return {"error": "Run not found or not completed"}
    all_records = get_run_evidence(result["run_id"])
    filtered = [r for r in all_records if r["agent_type"] == agent_type]
    return {"count": len(filtered), "records": filtered}


@app.get("/api/scan/{scan_id}/report")
def get_scan_report(scan_id: str):
    result = SCAN_STATUS.get(scan_id)
    if not result or result.get("status") != "completed":
        return {"error": "Report not ready or scan not found"}
    return {"report": result["report_json"], "markdown": result["report_markdown"]}
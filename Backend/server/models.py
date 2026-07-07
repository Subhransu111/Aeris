from pydantic import BaseModel
from typing import Optional, Any

class ScanRequest(BaseModel):
    repo_url: str
    app_name: str
    frontend_subdirectory: Optional[str] = None
    backend_subdirectory: Optional[str] = None
    tier: str = "free"
    registration_config: Optional[Any] = None

class ScanStatusResponse(BaseModel):
    scan_id: str
    status: str  # "queued" | "running" | "completed" | "failed"
    current_step: Optional[str] = None
    error: Optional[str] = None
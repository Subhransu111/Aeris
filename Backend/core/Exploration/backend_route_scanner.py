"""
Single entry point for route scanning regardless of backend framework -
Security Agent calls this instead of importing a specific framework's
scanner directly, so adding a new framework later doesn't require
changing security_agent.py.
"""
import os
from .api_route_scanner import scan_express_routes, resolve_base_paths
from .flask_route_scanner import scan_flask_routes
from .django_route_scanner import scan_django_routes


def detect_backend_framework(repo_path: str) -> str:
    if os.path.exists(os.path.join(repo_path, "manage.py")):
        return "django"
    if os.path.exists(os.path.join(repo_path, "package.json")):
        return "express"
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ("venv", ".git", "__pycache__")]
        for fname in files:
            if fname.endswith(".py"):
                try:
                    with open(os.path.join(root, fname), "r", encoding="utf-8", errors="ignore") as f:
                        if "Flask(" in f.read():
                            return "flask"
                except Exception:
                    continue
    return "unknown"


def scan_backend_routes(repo_path: str) -> list:
    framework = detect_backend_framework(repo_path)

    if framework == "express":
        return resolve_base_paths(repo_path, scan_express_routes(repo_path))
    if framework == "flask":
        return scan_flask_routes(repo_path)
    if framework == "django":
        return scan_django_routes(repo_path)

    return [] 
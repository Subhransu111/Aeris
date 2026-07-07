import json
import os

COMMON_SERVICE_DIRS = ["backend", "server", "api", "frontend", "client", "web", "app"]

def detect_stack(repo_path: str, subdirectory: str = None) -> dict:
    """
    If subdirectory is given, detect stack only within that folder.
    Otherwise, check root first, then auto-discover common service folders.
    """
    target_path = os.path.join(repo_path, subdirectory) if subdirectory else repo_path
    stack = _detect_in_path(target_path)

    if stack["framework"] != "unknown":
        stack["subdirectory"] = subdirectory
        return stack

    if subdirectory:
        return stack  # user explicitly pointed here, don't auto-search further

    # Root had nothing usable - scan for common service subfolders
    discovered_services = discover_services(repo_path)
    if discovered_services:
        return {
            "language": "multi_service",
            "framework": "multi_service",
            "default_port": None,
            "services": discovered_services
        }

    return stack


def discover_services(repo_path: str) -> list:
    """Scans known service-folder names for manifest files, returns list of detected services."""
    services = []
    for entry in os.listdir(repo_path):
        full_path = os.path.join(repo_path, entry)
        if not os.path.isdir(full_path):
            continue
        if entry.lower() in COMMON_SERVICE_DIRS or entry.lower() in [d.lower() for d in COMMON_SERVICE_DIRS]:
            stack = _detect_in_path(full_path)
            if stack["framework"] != "unknown":
                services.append({
                    "name": entry,
                    "path": entry,
                    "stack": stack
                })
    return services


def _detect_in_path(path: str) -> dict:
    pkg_path = os.path.join(path, "package.json")
    if os.path.exists(pkg_path):
        with open(pkg_path) as f:
            pkg = json.load(f)
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        entry_point = pkg.get("main", "index.js")
        start_script = pkg.get("scripts", {}).get("start")

        if "next" in deps:
            return {"language": "node", "framework": "nextjs", "default_port": 3000, "entry_point": entry_point, "start_script": start_script}
        if "vite" in deps or "vite" in pkg.get("scripts", {}).get("dev", ""):
            return {"language": "node", "framework": "vite", "default_port": 5173, "entry_point": entry_point, "start_script": pkg.get("scripts", {}).get("dev")}
        if "vue" in deps:
            return {"language": "node", "framework": "vue", "default_port": 8080, "entry_point": entry_point, "start_script": start_script}
        if "electron" in deps:
            return {"language": "node", "framework": "electron", "default_port": None, "entry_point": entry_point, "start_script": start_script}
        if "express" in deps:
            return {"language": "node", "framework": "express", "default_port": 3000, "entry_point": entry_point, "start_script": start_script}
        if "react" in deps:
            return {"language": "node", "framework": "react", "default_port": 3000, "entry_point": entry_point, "start_script": start_script}
        return {"language": "node", "framework": "node_generic", "default_port": 3000, "entry_point": entry_point, "start_script": start_script}

    req_path = os.path.join(path, "requirements.txt")
    if os.path.exists(req_path):
        with open(req_path) as f:
            content = f.read().lower()
        if "django" in content:
            return {"language": "python", "framework": "django", "default_port": 8000}
        if "fastapi" in content:
            return {"language": "python", "framework": "fastapi", "default_port": 8000}
        if "flask" in content:
            return {"language": "python", "framework": "flask", "default_port": 5000}
        if "streamlit" in content:
            return {"language": "python", "framework": "streamlit", "default_port": 8501}
        return {"language": "python", "framework": "python_generic", "default_port": 8000}

    if os.path.exists(os.path.join(path, "Dockerfile")):
        return {"language": "custom", "framework": "user_dockerfile", "default_port": None}

    return {"language": "unknown", "framework": "unknown", "default_port": None}
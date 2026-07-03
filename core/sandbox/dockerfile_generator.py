import os
import subprocess

TEMPLATES = {
    ("node", "nextjs"): "FROM node:20\nWORKDIR /app\nCOPY . .\nRUN npm install\nRUN npm run build\nCMD [\"npm\", \"start\"]\n",
    ("node", "react"):  "FROM node:20\nWORKDIR /app\nCOPY . .\nRUN npm install\nCMD [\"npm\", \"start\"]\n",
    ("node", "vite"):   "FROM node:20\nWORKDIR /app\nCOPY . .\nRUN npm install\nCMD [\"npm\", \"run\", \"dev\", \"--\", \"--host\"]\n",
    ("python", "django"):  "FROM python:3.11\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD [\"python\", \"manage.py\", \"runserver\", \"0.0.0.0:8000\"]\n",
    ("python", "fastapi"): "FROM python:3.11\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]\n",
    ("python", "flask"):   "FROM python:3.11\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD [\"python\", \"app.py\"]\n",
}

def generate_dockerfile(repo_path: str, stack: dict) -> dict:
    """
    Returns {"method": "user_dockerfile"|"template"|"buildpack"|"failed", "dockerfile_path": str|None}
    Never overwrites user's own Dockerfile.
    """
    if stack["framework"] == "user_dockerfile":
        return {"method": "user_dockerfile", "dockerfile_path": os.path.join(repo_path, "Dockerfile")}

    key = (stack["language"], stack["framework"])
    content = TEMPLATES.get(key)

    if content:
        out_path = os.path.join(repo_path, "Dockerfile.aegis")
        with open(out_path, "w") as f:
            f.write(content)
        return {"method": "template", "dockerfile_path": out_path}

    # Fallback: try Cloud Native Buildpacks (no Dockerfile needed at all)
    if _buildpacks_available():
        return {"method": "buildpack", "dockerfile_path": None}

    return {"method": "failed", "dockerfile_path": None}


def _buildpacks_available() -> bool:
    try:
        result = subprocess.run(["pack", "version"], capture_output=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def build_with_buildpack(repo_path: str, tag: str, timeout_seconds: int = 600) -> dict:
    """Builds image using pack CLI (auto-detects language, no Dockerfile required)."""
    try:
        result = subprocess.run(
            ["pack", "build", tag, "--path", repo_path, "--builder", "paketobuildpacks/builder-jammy-base"],
            capture_output=True,
            timeout=timeout_seconds,
            text=True
        )
        success = result.returncode == 0
        return {
            "success": success,
            "logs": result.stdout + result.stderr
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "logs": "buildpack build timed out"}
    except Exception as e:
        return {"success": False, "logs": str(e)}
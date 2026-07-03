import json
import os

def detect_stack(repo_path: str) -> dict:
    pkg_path = os.path.join(repo_path, "package.json")
    if os.path.exists(pkg_path):
        with open(pkg_path) as f:
            pkg = json.load(f)
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if "next" in deps:
            return {"language": "node", "framework": "nextjs", "default_port": 3000}
        if "vite" in deps:
            return {"language": "node", "framework": "vite", "default_port": 5173}
        if "vue" in deps:
            return {"language": "node", "framework": "vue", "default_port": 8080}
        if "electron" in deps:
            return {"language": "node", "framework": "electron", "default_port": None}
        if "react" in deps:
            return {"language": "node", "framework": "react", "default_port": 3000}
        return {"language": "node", "framework": "unknown", "default_port": 3000}

    req_path = os.path.join(repo_path, "requirements.txt")
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
        return {"language": "python", "framework": "unknown", "default_port": 8000}

    if os.path.exists(os.path.join(repo_path, "Dockerfile")):
        return {"language": "custom", "framework": "user_dockerfile", "default_port": None}

    return {"language": "unknown", "framework": "unknown", "default_port": None}
"""
Scans Flask apps for route definitions. Flask's decorator-based routing
(@app.route, @bp.route) requires different regex than Express's chained-
call style, but produces the same output shape so downstream Security
Agent code doesn't need to know which framework it's looking at.
"""
import os
import re

ROUTE_PATTERN = re.compile(
    r'@(?:app|bp|blueprint)\.route\(\s*[\'"]([^\'"]+)[\'"](?:.*?methods\s*=\s*\[([^\]]*)\])?',
    re.IGNORECASE | re.DOTALL
)
AUTH_DECORATOR_PATTERN = re.compile(r'@(login_required|jwt_required|auth_required|requires_auth)', re.IGNORECASE)


def scan_flask_routes(repo_path: str) -> list:
    routes = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ("venv", ".git", "__pycache__", "node_modules")]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            full_path = os.path.join(root, fname)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            for match in ROUTE_PATTERN.finditer(content):
                path, methods_str = match.groups()
                methods = [m.strip().strip("'\"") for m in methods_str.split(",")] if methods_str else ["GET"]

                line_start = content.rfind("\n", 0, match.start())
                context_before = content[max(0, line_start - 200):match.start()]
                likely_protected = bool(AUTH_DECORATOR_PATTERN.search(context_before))

                for method in methods:
                    routes.append({
                        "method": method.upper(), "path": path,
                        "file": os.path.relpath(full_path, repo_path),
                        "likely_protected": likely_protected,
                    })
    return routes
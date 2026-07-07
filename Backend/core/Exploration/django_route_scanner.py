"""
Scans Django urls.py files. Django's routing is centralized (urlpatterns
lists) rather than decorator-scattered, and auth is typically enforced in
the view function/class, not visible from urls.py alone - so
likely_protected here checks the view file for @login_required or
LoginRequiredMixin as a heuristic, accepting lower precision than Express/Flask.
"""
import os
import re

URLPATTERN_PATTERN = re.compile(r'path\(\s*[\'"]([^\'"]*)[\'"]\s*,\s*([.\w]+)')
VIEW_AUTH_PATTERN = re.compile(r'(login_required|LoginRequiredMixin|IsAuthenticated|permission_classes)', re.IGNORECASE)


def scan_django_routes(repo_path: str) -> list:
    routes = []
    view_files_content = {}

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ("venv", ".git", "__pycache__", "node_modules", "migrations")]
        for fname in files:
            if fname == "views.py" or fname.endswith("_views.py"):
                full_path = os.path.join(root, fname)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        view_files_content[full_path] = f.read()
                except Exception:
                    continue

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ("venv", ".git", "__pycache__", "node_modules", "migrations")]
        for fname in files:
            if fname != "urls.py":
                continue
            full_path = os.path.join(root, fname)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            for match in URLPATTERN_PATTERN.finditer(content):
                path, view_ref = match.groups()
                likely_protected = any(
                    VIEW_AUTH_PATTERN.search(vcontent) for vcontent in view_files_content.values()
                    if view_ref.split(".")[-1] in vcontent
                )
                routes.append({
                    "method": "GET",  # Django urls.py doesn't specify method directly - conservative default
                    "path": "/" + path.lstrip("/"),
                    "file": os.path.relpath(full_path, repo_path),
                    "likely_protected": likely_protected,
                })
    return routes
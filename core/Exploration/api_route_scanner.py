import os
import re

ROUTE_PATTERN = re.compile(
    r'router\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
    re.IGNORECASE
)
APP_ROUTE_PATTERN = re.compile(
    r'app\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
    re.IGNORECASE
)
MIDDLEWARE_AUTH_PATTERN = re.compile(r'(authenticate|isAuth|verifyToken|requireAuth|protect)', re.IGNORECASE)

def scan_express_routes(repo_path: str) -> list:
    """
    Scans .js files for Express route definitions.
    Returns list of {method, path, file, likely_protected}
    """
    routes = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git")]
        for fname in files:
            if not fname.endswith(".js"):
                continue
            full_path = os.path.join(root, fname)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            for pattern in (ROUTE_PATTERN, APP_ROUTE_PATTERN):
                for match in pattern.finditer(content):
                    method, path = match.groups()
                    # check nearby context (same line) for auth middleware usage
                    line_start = content.rfind("\n", 0, match.start()) + 1
                    line_end = content.find("\n", match.end())
                    line_context = content[line_start:line_end if line_end != -1 else None]
                    likely_protected = bool(MIDDLEWARE_AUTH_PATTERN.search(line_context))

                    routes.append({
                        "method": method.upper(),
                        "path": path,
                        "file": os.path.relpath(full_path, repo_path),
                        "likely_protected": likely_protected
                    })
    return routes


def resolve_base_paths(repo_path: str, routes: list) -> list:
    """
    Detects app.use('/api/x', router) mount points and prefixes route paths accordingly.
    """
    mount_pattern = re.compile(r'app\.use\s*\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*require\([\'"]([^\'"]+)[\'"]\)')
    mounts = {}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git")]
        for fname in files:
            if not fname.endswith(".js"):
                continue
            full_path = os.path.join(root, fname)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue
            for prefix, required_file in mount_pattern.findall(content):
                mounts[os.path.basename(required_file)] = prefix

    for route in routes:
        route_file_base = os.path.splitext(os.path.basename(route["file"]))[0]
        if route_file_base in mounts:
            route["path"] = mounts[route_file_base].rstrip("/") + "/" + route["path"].lstrip("/")

    return routes
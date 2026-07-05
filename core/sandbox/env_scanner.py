import os
import re

ENV_VAR_PATTERN = re.compile(r'process\.env\.([A-Z_][A-Z0-9_]*)')
VITE_ENV_VAR_PATTERN = re.compile(r'import\.meta\.env\.([A-Z_][A-Z0-9_]*)')

LOCALHOST_PATTERN = re.compile(r'localhost:\d{2,5}|127\.0\.0\.1:\d{2,5}')

FRONTEND_API_URL_VARS = [
    "REACT_APP_API_URL", "REACT_APP_BACKEND_URL", "REACT_APP_API_BASE_URL",
    "VITE_API_URL", "VITE_API_BASE_URL", "VITE_BACKEND_URL",
    "NEXT_PUBLIC_API_URL", "VUE_APP_API_URL",
]


def scan_env_vars(repo_path: str) -> set:
    """
    Recursively scans .js/.jsx/.ts/.tsx files for env var usage.
    Checks both process.env.X (Node/CRA/webpack style) and
    import.meta.env.X (Vite style) - missing the latter would silently
    break env injection for any Vite-based frontend.
    """
    found_vars = set()
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "dist", "build")]
        for fname in files:
            if fname.endswith((".js", ".jsx", ".ts", ".tsx")):
                try:
                    with open(os.path.join(root, fname), "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    found_vars.update(ENV_VAR_PATTERN.findall(content))
                    found_vars.update(VITE_ENV_VAR_PATTERN.findall(content))
                except Exception:
                    continue
    return found_vars


def generate_env_values(env_vars: set, db_info: dict = None, db_host: str = None, app_port: str = "5000") -> dict:
    values = {}
    for var in env_vars:
        upper = var.upper()
        if db_info and any(k in upper for k in ("MONGO", "DB_URI", "DATABASE_URL", "MONGODB")):
            values[var] = db_info["uri_env_hint"].format(host=db_host)
        elif "PORT" in upper:
            values[var] = app_port
        elif "SECRET" in upper or "KEY" in upper or "JWT" in upper:
            values[var] = "aegis_sandbox_dummy_secret_do_not_use_in_prod"
        elif "NODE_ENV" in upper:
            values[var] = "development"
        else:
            values[var] = "aegis_sandbox_placeholder"

    values.setdefault("HOST", "0.0.0.0")  # ensure dev servers bind externally
    values.setdefault("CI", "true")       # prevents CRA from opening interactive prompts
    return values


def generate_frontend_env_values(env_vars: set, backend_host: str, backend_port: int) -> dict:
    """
    Frontend apps typically read their backend URL from a build-time env var.
    Returns (values_dict, matched_any) - matched_any=False signals the
    frontend likely hardcodes its API URL instead, which env injection
    can't fix (see scan_hardcoded_localhost for that case).
    """
    values = {}
    backend_url = f"http://{backend_host}:{backend_port}"
    matched_any = False

    for var in env_vars:
        if var in FRONTEND_API_URL_VARS:
            values[var] = backend_url
            matched_any = True
        elif "API" in var.upper() and "URL" in var.upper():
            values[var] = backend_url
            matched_any = True
        elif "BACKEND" in var.upper() and "URL" in var.upper():
            values[var] = backend_url
            matched_any = True

    values.setdefault("HOST", "0.0.0.0")
    values.setdefault("CI", "true")
    return values, matched_any


def scan_hardcoded_localhost(repo_path: str) -> list:
    """
    Flags hardcoded localhost/127.0.0.1 URLs in frontend source - these
    break in a multi-container sandbox regardless of env injection, since
    'localhost' inside the frontend container refers to itself, not the
    backend container. A real, reportable finding for the developer.
    """
    findings = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "dist", "build")]
        for fname in files:
            if fname.endswith((".js", ".jsx", ".ts", ".tsx")):
                full_path = os.path.join(root, fname)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    for match in LOCALHOST_PATTERN.finditer(content):
                        line_num = content[:match.start()].count("\n") + 1
                        findings.append({
                            "file": os.path.relpath(full_path, repo_path),
                            "line": line_num,
                            "match": match.group(),
                        })
                except Exception:
                    continue
    return findings
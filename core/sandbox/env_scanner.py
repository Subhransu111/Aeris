import os
import re

ENV_VAR_PATTERN = re.compile(r'process\.env\.([A-Z_][A-Z0-9_]*)')

def scan_env_vars(repo_path: str) -> set:
    """Recursively scans .js files for process.env.X usage."""
    found_vars = set()
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git")]
        for fname in files:
            if fname.endswith(".js"):
                try:
                    with open(os.path.join(root, fname), "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    found_vars.update(ENV_VAR_PATTERN.findall(content))
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
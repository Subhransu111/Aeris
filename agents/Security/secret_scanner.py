"""
Scans source code for hardcoded secrets (API keys, tokens, credentials).
Pure static file reading - zero risk, zero cost, catches a genuinely
common and severe real-world mistake.
"""
import os
import re

SECRET_PATTERNS = {
    "AWS Access Key": re.compile(r'AKIA[0-9A-Z]{16}'),
    "Generic API Key": re.compile(r'(?i)api[_-]?key["\']?\s*[:=]\s*["\'][a-zA-Z0-9_\-]{20,}["\']'),
    "Stripe Secret Key": re.compile(r'sk_live_[0-9a-zA-Z]{24,}'),
    "Private Key Block": re.compile(r'-----BEGIN (RSA |EC )?PRIVATE KEY-----'),
    "JWT-looking Secret": re.compile(r'(?i)jwt[_-]?secret["\']?\s*[:=]\s*["\'][^"\']{10,}["\']'),
    "Generic Password Assignment": re.compile(r'(?i)password["\']?\s*[:=]\s*["\'][^"\']{6,}["\']'),
    "MongoDB URI with credentials": re.compile(r'mongodb(\+srv)?://[^:]+:[^@]+@'),
}

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next"}


def scan_for_secrets(repo_path: str) -> list:
    findings = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            if not fname.endswith((".js", ".ts", ".jsx", ".tsx", ".py", ".env", ".json", ".yml", ".yaml")):
                continue
            full_path = os.path.join(root, fname)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            for secret_type, pattern in SECRET_PATTERNS.items():
                for match in pattern.finditer(content):
                    line_num = content[:match.start()].count("\n") + 1
                    findings.append({
                        "check": "hardcoded_secret",
                        "secret_type": secret_type,
                        "file": os.path.relpath(full_path, repo_path),
                        "line": line_num,
                        "outcome": "vulnerable",
                        "severity": "critical",
                        "detail": f"{secret_type} pattern found - should be in environment variables, not source code",
                    })
    return findings
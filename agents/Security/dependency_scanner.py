"""
Wraps npm audit / pip-audit to find known vulnerable dependencies.
Zero new logic - just subprocess call + JSON parse, since these tools
already do the hard work (CVE database matching).
"""
import subprocess
import json
import os


def scan_npm_dependencies(repo_path: str) -> list:
    if not os.path.exists(os.path.join(repo_path, "package.json")):
        return []
    try:
        result = subprocess.run(
            ["npm", "audit", "--json"],
            cwd=repo_path, capture_output=True, text=True, timeout=60
        )
        data = json.loads(result.stdout) if result.stdout else {}
    except Exception:
        return []

    findings = []
    vulnerabilities = data.get("vulnerabilities", {})
    for pkg_name, vuln_info in vulnerabilities.items():
        severity = vuln_info.get("severity", "low")
        findings.append({
            "check": "vulnerable_dependency",
            "package": pkg_name,
            "outcome": "vulnerable",
            "severity": severity if severity in ("critical", "high") else "moderate" if severity == "moderate" else "low",
            "detail": f"Package '{pkg_name}' has known {severity} severity vulnerabilities",
        })
    return findings
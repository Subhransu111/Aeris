"""
Backend API security checks using routes discovered by api_route_scanner.py.
Read and reversible-write actions (GET, POST, PUT probes) route through the
Policy Engine as allow_sandbox_only - same risk class as form submissions
already permitted elsewhere. DELETE and payment routes stay blocked/mocked.
"""
import requests
import re
from core.core.action_wrapper import execute_action

SAFE_PROBE_PAYLOAD = {"aegis_test_field": "aegis_probe_value"}


def check_missing_auth(base_url: str, routes: list, agent_id: str, base_domain: str, verified_domain: str) -> list:
    """Unauthenticated request to routes the code flags as protected."""
    findings = []
    for route in routes:
        if not route.get("likely_protected"):
            continue
        if route["method"] == "DELETE":
            continue  # never probe delete endpoints, even unauthenticated

        action_type = {
            "GET": "get_request", "POST": "api_post_probe",
            "PUT": "api_put_probe", "PATCH": "api_put_probe",
        }.get(route["method"], "get_request")

        decision = execute_action(agent_id, {
            "type": action_type, "target_domain": base_domain, "verified_domain": verified_domain
        }, sandbox_mode=True)
        if decision["status"] != "executed":
            continue

        full_url = base_url.rstrip("/") + route["path"]
        try:
            if route["method"] == "GET":
                resp = requests.get(full_url, timeout=5)
            else:
                resp = requests.request(route["method"], full_url, json=SAFE_PROBE_PAYLOAD, timeout=5)

            if resp.status_code in (200, 201):
                findings.append({
                    "check": "missing_auth_enforcement",
                    "route": route["path"], "method": route["method"],
                    "outcome": "vulnerable", "severity": "critical",
                    "detail": f"Route flagged as protected in code but returned {resp.status_code} without authentication",
                })
        except requests.exceptions.RequestException:
            continue
    return findings


def check_idor_pattern(base_url: str, routes: list, agent_id: str, base_domain: str, verified_domain: str) -> list:
    """
    Static pattern check (no auth needed): flags GET routes with a numeric
    or predictable ID in the path (e.g. /api/users/:id, /api/orders/1) as
    IDOR candidates worth manual review. This doesn't confirm IDOR (needs
    two real accounts to test properly - flagged as a future capability),
    but surfaces the attack surface cheaply via static analysis alone.
    """
    findings = []
    id_pattern = re.compile(r'/:(\w*id\w*)|/\d+(?:/|$)', re.IGNORECASE)

    for route in routes:
        if route["method"] == "GET" and id_pattern.search(route["path"]):
            findings.append({
                "check": "idor_candidate",
                "route": route["path"], "method": route["method"],
                "outcome": "needs_manual_review",
                "severity": "moderate",
                "detail": "Route accepts an ID parameter - verify server checks the requester owns this resource (requires two test accounts to confirm)",
            })
    return findings


def check_rate_limiting(base_url: str, route_path: str, agent_id: str, base_domain: str,
                         verified_domain: str, request_count: int = 20) -> dict:
    decision = execute_action(agent_id, {
        "type": "get_request", "target_domain": base_domain, "verified_domain": verified_domain
    }, sandbox_mode=True)
    if decision["status"] != "executed":
        return {"check": "rate_limiting", "outcome": decision["status"]}

    full_url = base_url.rstrip("/") + route_path
    statuses = []
    for _ in range(request_count):
        try:
            resp = requests.get(full_url, timeout=3)
            statuses.append(resp.status_code)
        except requests.exceptions.RequestException:
            break

    hit_rate_limit = 429 in statuses
    return {
        "check": "rate_limiting", "route": route_path,
        "outcome": "protected" if hit_rate_limit else "no_rate_limit_detected",
        "severity": "info" if hit_rate_limit else "moderate",
        "detail": f"{len(statuses)} requests sent, rate limit {'triggered' if hit_rate_limit else 'not triggered'}",
    }


def check_open_redirect(base_url: str, agent_id: str, base_domain: str, verified_domain: str) -> list:
    """Tests common redirect-param names with an external URL - cheap, common vuln class."""
    decision = execute_action(agent_id, {
        "type": "get_request", "target_domain": base_domain, "verified_domain": verified_domain
    }, sandbox_mode=True)
    if decision["status"] != "executed":
        return []

    findings = []
    redirect_params = ["redirect", "return", "returnUrl", "next", "url", "continue"]
    probe_target = "https://example.com/aegis-redirect-probe"

    for param in redirect_params:
        try:
            resp = requests.get(f"{base_url}/?{param}={probe_target}", timeout=5, allow_redirects=False)
            location = resp.headers.get("Location", "")
            if "example.com" in location:
                findings.append({
                    "check": "open_redirect", "param": param,
                    "outcome": "vulnerable", "severity": "moderate",
                    "detail": f"Parameter '{param}' redirects to arbitrary external URL",
                })
        except requests.exceptions.RequestException:
            continue
    return findings
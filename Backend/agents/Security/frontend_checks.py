"""
Frontend security checks building on functional_agent.py's existing form
submission infrastructure. Reuses the same fill-and-submit mechanism but
inspects the RESPONSE for signs of vulnerability rather than just checking
if validation triggered. Read-only in intent: payloads are non-destructive
probes (detection strings), never actual exploitation payloads.
"""
import json

from Backend.core.core.action_wrapper import execute_action


REFLECTED_XSS_MARKER = "AEGISXSSPROBE12345"
SQLI_ERROR_SIGNATURES = [
    "sql syntax", "mysql_fetch", "ora-01756", "sqlstate", "pg_query",
    "sqlite3.operationalerror", "unclosed quotation mark", "syntax error near",
]


def check_reflected_xss(page, form: dict, agent_id: str, base_domain: str, verified_domain: str) -> dict:
    action = {"type": "form_submit", "target_domain": base_domain, "verified_domain": verified_domain}
    decision = execute_action(agent_id, action, sandbox_mode=True)
    if decision["status"] != "executed":
        return {"check": "reflected_xss", "outcome": decision["status"], "detail": "Not executed - policy decision"}

    try:
        for field in form["fields"]:
            if field.get("selector") and field.get("type", "").lower() not in ("password", "checkbox", "radio", "file"):
                page.fill(field["selector"], REFLECTED_XSS_MARKER, timeout=3000)

        submit_selector = form.get("submit_selector")
        if submit_selector:
            page.click(submit_selector, timeout=5000)
        page.wait_for_timeout(1000)

        
        marker_in_dom = page.evaluate(f"""
            () => document.body.innerHTML.includes({json.dumps(REFLECTED_XSS_MARKER)})
        """)


        marker_unescaped = page.evaluate(f"""
            () => {{
                const marker = {json.dumps(REFLECTED_XSS_MARKER)};
                const html = document.body.innerHTML;
                const idx = html.indexOf(marker);
                if (idx === -1) return false;
                // If surrounded by escaped entities nearby, it's likely safely rendered as text
                const before = html.substring(Math.max(0, idx - 20), idx);
                return !before.includes('&lt;') && !before.includes('&quot;');
            }}
        """)

        vulnerable = marker_in_dom and marker_unescaped

        return {
            "check": "reflected_xss",
            "outcome": "vulnerable" if vulnerable else "not_reflected",
            "severity": "critical" if vulnerable else "info",
            "detail": "Input marker reflected unescaped in rendered DOM" if vulnerable else "Marker not found in an executable HTML context (may appear in API response only, which is not exploitable)",
        }
    except Exception as e:
        return {"check": "reflected_xss", "outcome": "check_failed", "detail": str(e)[:200]}

def check_sqli_error_disclosure(page, form: dict, agent_id: str, base_domain: str, verified_domain: str) -> dict:
    """
    Submits a single-quote probe (classic SQLi detection string) and checks
    if the response leaks a database error message - a strong signal of
    an unparameterized query, without needing a full exploit chain.
    """
    action = {"type": "form_submit", "target_domain": base_domain, "verified_domain": verified_domain}
    decision = execute_action(agent_id, action, sandbox_mode=True)
    if decision["status"] != "executed":
        return {"check": "sqli_error_disclosure", "outcome": decision["status"], "detail": "Not executed - policy decision"}

    try:
        for field in form["fields"]:
            if field.get("selector") and field.get("type", "").lower() not in ("password", "checkbox", "radio", "file"):
                page.fill(field["selector"], "'", timeout=3000)

        submit_selector = form.get("submit_selector")
        if submit_selector:
            page.click(submit_selector, timeout=5000)
        page.wait_for_timeout(1000)

        content = page.content().lower()
        leaked = any(sig in content for sig in SQLI_ERROR_SIGNATURES)

        return {
            "check": "sqli_error_disclosure",
            "outcome": "vulnerable" if leaked else "not_detected",
            "severity": "critical" if leaked else "info",
            "detail": "Database error message leaked in response" if leaked else "No SQL error signature found",
        }
    except Exception as e:
        return {"check": "sqli_error_disclosure", "outcome": "check_failed", "detail": str(e)[:200]}
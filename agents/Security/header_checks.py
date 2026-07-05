"""
Checks HTTP response headers for common security misconfigurations.
Pure read-only - just inspects headers already present on any response,
no additional requests beyond what's already happening during crawl.
"""

REQUIRED_HEADERS = {
    "x-content-type-options": "Missing X-Content-Type-Options - allows MIME-sniffing attacks",
    "x-frame-options": "Missing X-Frame-Options - page can be embedded in iframe (clickjacking risk)",
    "content-security-policy": "Missing Content-Security-Policy - reduced protection against XSS",
    "strict-transport-security": "Missing Strict-Transport-Security - no HSTS enforcement",
}

def check_cors_misconfiguration(page, api_url: str, frontend_origin: str) -> dict:
    """
    Tests whether the backend's CORS policy actually permits the frontend's
    real origin - if a fixed dev port is hardcoded, this fails in any
    environment (including production) where the frontend runs elsewhere.
    """
    try:
        result = page.evaluate(f"""
            async () => {{
                try {{
                    const resp = await fetch("{api_url}", {{
                        method: "OPTIONS",
                        headers: {{ "Origin": "{frontend_origin}" }}
                    }});
                    return {{
                        status: resp.status,
                        allow_origin: resp.headers.get("access-control-allow-origin")
                    }};
                }} catch (e) {{
                    return {{ error: e.message }};
                }}
            }}
        """)
    except Exception as e:
        return {"check": "cors_configuration", "outcome": "check_failed", "detail": str(e)[:200]}

    if result.get("error") or not result.get("allow_origin"):
        return {
            "check": "cors_configuration",
            "outcome": "misconfigured",
            "severity": "moderate",
            "detail": f"Backend does not send Access-Control-Allow-Origin for frontend's actual origin ({frontend_origin}) - likely hardcoded to a fixed dev URL, which will also break in staging/production if frontend origin differs",
        }
    return {"check": "cors_configuration", "outcome": "correctly_configured", "severity": "info"}


def check_response_headers(headers: dict) -> list:
    """headers: dict of response headers (lowercase keys expected)."""
    findings = []
    lower_headers = {k.lower(): v for k, v in headers.items()}

    for header, message in REQUIRED_HEADERS.items():
        if header not in lower_headers:
            findings.append({
                "check": "missing_security_header",
                "header": header,
                "detail": message,
                "severity": "moderate",
            })

    server_header = lower_headers.get("server", "")
    if server_header and any(c.isdigit() for c in server_header):
        findings.append({
            "check": "server_version_disclosure",
            "detail": f"Server header discloses version info: '{server_header}'",
            "severity": "low",
        })

    return findings
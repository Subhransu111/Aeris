"""
Security Agent: coordinates all security checks. Ordered cheapest-first
(static analysis needs no browser/network) before browser-dependent checks,
so a fast run gets the highest-value findings even if later steps time out.
"""
from urllib.parse import urlparse
from agents.Security.frontend_checks import check_reflected_xss, check_sqli_error_disclosure
from agents.Security.api_checks import check_missing_auth, check_idor_pattern, check_rate_limiting, check_open_redirect
from agents.Security.header_checks import check_response_headers
from agents.Security.secret_scanner import scan_for_secrets
from agents.Security.dependency_scanner import scan_npm_dependencies
from agents.Security.clickjacking_check import check_clickjacking
from core.Exploration.backend_route_scanner import scan_backend_routes

def run_security_agent(page, sitemap: dict, base_url: str, verified_domain: str,
                         backend_repo_path: str = None, backend_base_url: str = None,
                         agent_id: str = "security_agent") -> list:
    evidence = []
    base_domain = urlparse(base_url).netloc

    if backend_repo_path:
        for finding in scan_for_secrets(backend_repo_path):
            evidence.append({"todo_type": "security_check", "url": base_url, **finding})
        for finding in scan_npm_dependencies(backend_repo_path):
            evidence.append({"todo_type": "security_check", "url": base_url, **finding})

    if backend_repo_path and backend_base_url:
        routes = scan_backend_routes(backend_repo_path)  
        backend_domain = urlparse(backend_base_url).netloc
        for finding in check_missing_auth(backend_base_url, routes, agent_id, backend_domain, backend_domain):
            evidence.append({"todo_type": "security_check", "url": backend_base_url, **finding})
        for finding in check_idor_pattern(backend_base_url, routes, agent_id, backend_domain, backend_domain):
            evidence.append({"todo_type": "security_check", "url": backend_base_url, **finding})

        unprotected_get = [r for r in routes if r["method"] == "GET" and not r.get("likely_protected")]
        for route in unprotected_get[:3]:
            evidence.append({"todo_type": "security_check", "url": backend_base_url + route["path"],
                              **check_rate_limiting(backend_base_url, route["path"], agent_id, backend_domain, backend_domain)})

    for finding in check_open_redirect(base_url, agent_id, base_domain, verified_domain):
        evidence.append({"todo_type": "security_check", "url": base_url, **finding})

    evidence.append({"todo_type": "security_check", "url": base_url,
                      **check_clickjacking(page, base_url)})

    for page_key, page_data in sitemap["pages"].items():
        if not page_data.get("reachable"):
            continue
        url = page_data.get("url")
        try:
            response = page.goto(url, wait_until="load", timeout=15000)
            if response:
                for finding in check_response_headers(response.all_headers()):
                    evidence.append({"todo_type": "security_check", "url": url, **finding})
        except Exception:
            continue

        for form in page_data.get("forms", []):
            try:
                page.goto(url, wait_until="load", timeout=15000)
                page.wait_for_timeout(500)
            except Exception:
                continue
            evidence.append({"todo_type": "security_check", "url": url,
                              **check_reflected_xss(page, form, agent_id, base_domain, verified_domain)})

            try:
                page.goto(url, wait_until="load", timeout=15000)
                page.wait_for_timeout(500)
            except Exception:
                continue
            evidence.append({"todo_type": "security_check", "url": url,
                              **check_sqli_error_disclosure(page, form, agent_id, base_domain, verified_domain)})

    return evidence
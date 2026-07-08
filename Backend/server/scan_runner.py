"""
Single pipeline: run_full_scan() creates its own sandbox and runs
everything through to a finished report. No session/detection split.
"""
import os
import json
import time
from importlib_metadata import metadata
import requests
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

from core.sandbox.sandbox_manager import create_sandbox, teardown_sandbox, teardown_multi_service_sandbox
from core.sandbox.execution_context import ExecutionContext
from core.Exploration.site_explorer import crawl
from agents.functional.test_planner import build_site_test_plan
from agents.functional.functional_agent import run_functional_agent
from agents.accessibility.accessibility_agent import run_accessibility_agent
from agents.Security.security_agent import run_security_agent
from agents.performance.performance_agent import run_performance_agent
from agents.journey.journey_agent import run_journey_agent
from core.evidence.evidence_store import start_run, finish_run, save_evidence
from agents.cto.evidence_summarizer import summarize_evidence, build_run_metadata
from agents.cto.cto_agent import generate_cto_report
from agents.cto.report_formatter import format_report_markdown
from agents.cto.providers.gemini_provider import GeminiProvider
from agents.provisioning.ensure_test_account import ensure_test_account

SCAN_STATUS = {}


def wait_for_server_ready(url: str, max_wait_seconds: int = 20) -> bool:
    deadline = time.time() + max_wait_seconds
    consecutive_ok = 0
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code < 500:
                consecutive_ok += 1
                if consecutive_ok >= 2:
                    return True
            else:
                consecutive_ok = 0
        except requests.exceptions.RequestException:
            consecutive_ok = 0
        time.sleep(1)
    return False


def _update_status(scan_id: str, step: str, status: str = "running", extra: dict = None):
    entry = {"status": status, "current_step": step, **(extra or {})}
    if status == "failed" and "error" not in entry:
        entry["error"] = entry.get("reason") or entry.get("detail") or "Unknown error"
    SCAN_STATUS[scan_id] = entry


def _resolve_signup_url(target_url: str, signup_url: str) -> str:
    """
    Handles both relative paths ('/register') and full URLs the developer
    might mistakenly supply - if signup_url already has a scheme/host,
    use it as-is; otherwise join it onto the sandbox's actual target_url.
    """
    parsed = urlparse(signup_url)
    if parsed.scheme and parsed.netloc:
        return signup_url  # already a full URL
    return target_url.rstrip("/") + "/" + signup_url.lstrip("/")


def run_full_scan(scan_id: str, repo_url: str, app_name: str,
                    frontend_subdir: str = None, backend_subdir: str = None,
                    tier: str = "free", registration_config: dict = None):

    _update_status(scan_id, "starting_sandbox")
    context = ExecutionContext(project_id=scan_id, org_id="platform", subscription_tier=tier,
                                max_memory_mb=512, max_cpu_percent=50, timeout_seconds=900)

    sandbox_result = create_sandbox(
        repo_url, context,
        frontend_subdir=frontend_subdir or "Frontend",
        backend_subdir=backend_subdir or "Backend",
    )

    if sandbox_result["status"] != "running":
        SCAN_STATUS[scan_id] = {"status": "failed", "error": json.dumps(sandbox_result, default=str)}
        return

    target_url = f"http://127.0.0.1:{sandbox_result['host_port']}"
    verified_domain = f"127.0.0.1:{sandbox_result['host_port']}"
    backend_base_url = None
    backend_path = None
    if "backend_host_port" in sandbox_result:
        backend_base_url = f"http://127.0.0.1:{sandbox_result['backend_host_port']}"
    if backend_subdir and os.path.isdir(os.path.join(sandbox_result["dest_dir"], backend_subdir)):
        backend_path = os.path.join(sandbox_result["dest_dir"], backend_subdir)

    _update_status(scan_id, "waiting_for_server")
    if not wait_for_server_ready(target_url):
        SCAN_STATUS[scan_id] = {"status": "failed", "error": "Frontend server did not become ready in time"}
        if sandbox_result and "frontend_container" in sandbox_result:
            teardown_multi_service_sandbox(sandbox_result)
        else:
            teardown_sandbox(sandbox_result)
        return

    run_id = start_run(target_url)
    credentials = None

    try:
        if registration_config:
            _update_status(scan_id, "provisioning_account")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--disable-web-security"])
                page = browser.new_page()
                cfg = dict(registration_config)
                cfg["signup_url"] = _resolve_signup_url(target_url, cfg["signup_url"])
                provision_result = ensure_test_account(page, cfg, verified_domain, verified_domain)
                try: browser.close()
                except Exception: pass

            if provision_result["status"] == "ready":
                credentials = provision_result["credentials"]
                _update_status(scan_id, "account_ready", extra={"method": provision_result["method"]})
            else:
                _update_status(scan_id, "authentication_failed_continuing", extra={
                    "auth_failure_reason": provision_result.get("reason"),
                    "auth_failure_log": provision_result.get("log"),
                })
                credentials = None

            
        _update_status(scan_id, "crawling")
        sitemap = crawl(target_url, max_pages=20, timeout_seconds=120,
                         run_interactions=True, credentials=credentials)

        auth_pages_reached = len([
            k for k, p in sitemap["pages"].items()
            if p.get("auth_state") == "authenticated" and k != "__login_attempt__"
        ])
        _update_status(scan_id, "crawling", extra={
            "pages_found": len(sitemap["pages"]),
            "authenticated_pages": auth_pages_reached,
            "sitemap": sitemap,
        })

        _update_status(scan_id, "functional_agent")
        todo = build_site_test_plan(sitemap)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-web-security"])
            page = browser.new_page()
            functional_evidence = run_functional_agent(page, todo, target_url, verified_domain=verified_domain)
            try: browser.close()
            except Exception: pass
        save_evidence(run_id, "functional", functional_evidence)

        _update_status(scan_id, "accessibility_agent")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-web-security"])
            page = browser.new_page()
            accessibility_evidence = run_accessibility_agent(sitemap, page)
            try: browser.close()
            except Exception: pass
        save_evidence(run_id, "accessibility", accessibility_evidence)

        _update_status(scan_id, "security_agent")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-web-security"])
            page = browser.new_page()
            security_evidence = run_security_agent(
                page, sitemap, target_url, verified_domain,
                backend_repo_path=backend_path if backend_path else None,
                backend_base_url=backend_base_url if backend_base_url else None,
            )
            try: browser.close()
            except Exception: pass
        save_evidence(run_id, "security", security_evidence)

        _update_status(scan_id, "performance_agent")
        performance_evidence = run_performance_agent(sitemap, backend_base_url=backend_base_url, tier=tier)
        save_evidence(run_id, "performance", performance_evidence)

        _update_status(scan_id, "journey_agent")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-web-security"])
            page = browser.new_page()
            journey_evidence = run_journey_agent(page, sitemap, verified_domain, verified_domain)
            try: browser.close()
            except Exception: pass
        save_evidence(run_id, "journey", journey_evidence)

        _update_status(scan_id, "generating_report")
        all_evidence = {
            "functional": functional_evidence, "accessibility": accessibility_evidence,
            "security": security_evidence, "performance": performance_evidence,
            "journey": journey_evidence,
        }
        summary = summarize_evidence(all_evidence)
        metadata = build_run_metadata(sitemap, all_evidence, app_name=app_name)
        metadata["registration_attempted"] = registration_config is not None
        metadata["registration_succeeded"] = credentials is not None

        provider = GeminiProvider()
        cto_result = generate_cto_report(summary, metadata, provider)

        if cto_result["status"] == "success":
            markdown = format_report_markdown(cto_result["report"], app_name=app_name)
            SCAN_STATUS[scan_id] = {
                "status": "completed", "run_id": run_id,
                "report_json": cto_result["report"], "report_markdown": markdown,
                "pages_found": len(sitemap["pages"]), "authenticated_pages": auth_pages_reached,
                "sitemap": sitemap,
            }
        else:
            SCAN_STATUS[scan_id] = {"status": "failed", "error": str(cto_result)}

    except Exception as e:
        SCAN_STATUS[scan_id] = {"status": "failed", "error": str(e)}
    finally:
        finish_run(run_id)
        if sandbox_result and "frontend_container" in sandbox_result:
            teardown_multi_service_sandbox(sandbox_result)
        else:
            teardown_sandbox(sandbox_result)
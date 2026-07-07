"""
Wraps the entire existing pipeline (unchanged) as a background-runnable
function. This is literally test_final_pipeline.py's logic, just
parameterized and reporting progress into a shared status dict instead
of printing to console.
"""
import json

# Keep these imports local so the FastAPI app can start without requiring
# Docker, Playwright, or other runtime dependencies during module import.

# In-memory status tracking (swap for Redis/DB in production, fine for now)
SCAN_STATUS = {}


def run_full_scan(scan_id: str, repo_url: str, app_name: str,
                    frontend_subdir: str = None, backend_subdir: str = None, tier: str = "free",
                    registration_config: dict = None):
    from playwright.sync_api import sync_playwright
    from Backend.core.sandbox.sandbox_manager import create_multi_service_sandbox, teardown_multi_service_sandbox
    from Backend.core.sandbox.execution_context import ExecutionContext
    from Backend.core.Exploration.site_explorer import crawl
    from Backend.agents.functional.test_planner import build_site_test_plan
    from Backend.agents.functional.functional_agent import run_functional_agent
    from Backend.agents.accessibility.accessibility_agent import run_accessibility_agent
    from Backend.agents.Security.security_agent import run_security_agent
    from Backend.agents.performance.performance_agent import run_performance_agent
    from Backend.agents.journey.journey_agent import run_journey_agent
    from Backend.core.evidence.evidence_store import start_run, finish_run, save_evidence
    from Backend.agents.cto.evidence_summarizer import summarize_evidence, build_run_metadata
    from Backend.agents.cto.cto_agent import generate_cto_report
    from Backend.agents.cto.report_formatter import format_report_markdown
    from Backend.agents.cto.providers.gemini_provider import GeminiProvider

    def update_status(step: str, status: str = "running", error: str = None):
        SCAN_STATUS[scan_id] = {
            "status": status,
            "current_step": step,
            "error": error,
        }

    sandbox_result = None
    run_id = None

    try:
        update_status("starting_sandbox")
        context = ExecutionContext(project_id=scan_id, org_id="platform", subscription_tier=tier,
                                    max_memory_mb=512, max_cpu_percent=50, timeout_seconds=900)

        sandbox_result = create_multi_service_sandbox(repo_url, context)

        if sandbox_result["status"] != "running":
            update_status("sandbox_failed", "failed", json.dumps(sandbox_result, default=str))
            return

        target_url = f"http://127.0.0.1:{sandbox_result['host_port']}"
        verified_domain = f"127.0.0.1:{sandbox_result['host_port']}"
        backend_base_url = f"http://127.0.0.1:{sandbox_result['backend_host_port']}"
        backend_path = f"{sandbox_result['dest_dir']}\\{backend_subdir or 'Backend'}"

        run_id = start_run(target_url)

        try:
            update_status("crawling")
            sitemap = crawl(target_url, max_pages=20, timeout_seconds=120, run_interactions=True)

            update_status("functional_agent")
            todo = build_site_test_plan(sitemap)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--disable-web-security"])
                page = browser.new_page()
                functional_evidence = run_functional_agent(page, todo, target_url, verified_domain=verified_domain)
                try:
                    browser.close()
                except Exception:
                    pass
            save_evidence(run_id, "functional", functional_evidence)

            update_status("accessibility_agent")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--disable-web-security"])
                page = browser.new_page()
                accessibility_evidence = run_accessibility_agent(sitemap, page)
                try:
                    browser.close()
                except Exception:
                    pass
            save_evidence(run_id, "accessibility", accessibility_evidence)

            update_status("security_agent")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--disable-web-security"])
                page = browser.new_page()
                security_evidence = run_security_agent(page, sitemap, target_url, verified_domain,
                                                      backend_repo_path=backend_path, backend_base_url=backend_base_url)
                try:
                    browser.close()
                except Exception:
                    pass
            save_evidence(run_id, "security", security_evidence)

            update_status("performance_agent")
            performance_evidence = run_performance_agent(sitemap, backend_base_url=backend_base_url, tier=tier)
            save_evidence(run_id, "performance", performance_evidence)

            update_status("journey_agent")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--disable-web-security"])
                page = browser.new_page()
                journey_evidence = run_journey_agent(page, sitemap, verified_domain, verified_domain)
                try:
                    browser.close()
                except Exception:
                    pass
            save_evidence(run_id, "journey", journey_evidence)

            update_status("generating_report")
            all_evidence = {
                "functional": functional_evidence, "accessibility": accessibility_evidence,
                "security": security_evidence, "performance": performance_evidence,
                "journey": journey_evidence,
            }
            summary = summarize_evidence(all_evidence)
            metadata = build_run_metadata(sitemap, all_evidence, app_name=app_name)
            provider = GeminiProvider()  # reads GEMINI_API_KEY from environment
            cto_result = generate_cto_report(summary, metadata, provider)

            if cto_result["status"] == "success":
                markdown = format_report_markdown(cto_result["report"], app_name=app_name)
                SCAN_STATUS[scan_id] = {
                    "status": "completed", "run_id": run_id,
                    "report_json": cto_result["report"], "report_markdown": markdown,
                }
            else:
                SCAN_STATUS[scan_id] = {"status": "failed", "error": str(cto_result)}

        except Exception as exc:
            update_status("scan_exception", "failed", str(exc)[:1000])
        finally:
            try:
                finish_run(run_id)
            except Exception:
                pass
            try:
                teardown_multi_service_sandbox(sandbox_result)
            except Exception:
                pass
    except Exception as exc:
        update_status("scan_exception", "failed", str(exc)[:1000])
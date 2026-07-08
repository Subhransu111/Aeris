"""
Performance Agent: Lighthouse for frontend page performance, k6 for API
load testing. Load tests are tier-gated and budget-capped by design -
this agent NEVER decides its own concurrency; that's Budget Enforcer's
job, enforced regardless of what this agent requests.
"""
from .lighthouse_runner import run_lighthouse
from .load_test_runner import run_load_test
from core.budget.resource_limits import get_limits


def run_performance_agent(sitemap: dict, backend_base_url: str = None,
                            tier: str = "free", max_pages_to_test: int = 5) -> list:
    evidence = []
    limits = get_limits(tier)

    # --- Frontend: Lighthouse per page (capped to avoid excessive runtime) ---
    tested = 0
    seen_urls = set()
    for page_key, page_data in sitemap["pages"].items():
        if tested >= max_pages_to_test:
            break
        url = page_data.get("url")
        if not url or url in seen_urls or not page_data.get("reachable"):
            continue
        seen_urls.add(url)

        result = run_lighthouse(url)
        if result["status"] == "completed":
            severity = "needs_review" if result["performance_score"] < 50 else \
                       "low" if result["performance_score"] < 90 else "info"
            evidence.append({
                "todo_type": "performance_check", "check": "lighthouse",
                "url": url, "outcome": "completed",
                "performance_score": result["performance_score"],
                "metrics": result["metrics"],
                "opportunities": result["opportunities"],
                "severity": severity,
            })
        else:
            evidence.append({
                "todo_type": "performance_check", "check": "lighthouse",
                "url": url, "outcome": result["status"], "detail": result.get("detail"),
            })
        tested += 1

    # --- Backend: load test, tier-appropriate defaults, always starts small ---
    if backend_base_url:
        # Conservative default test - well within free tier limits, safe to run
        # automatically. Larger tests require explicit developer confirmation,
        # enforced by Budget Enforcer, not this agent's judgment.
        default_users = min(20, limits["max_concurrent_users"])
        default_duration = min(30, limits["max_test_duration_seconds"])

        result = run_load_test(backend_base_url, tier, default_users, default_duration,
                                 developer_confirmed=False)

        if result["status"] == "completed":
            severity = "needs_review" if result.get("failed_request_rate", 0) > 0.05 else "info"
            evidence.append({
                "todo_type": "performance_check", "check": "load_test",
                "url": backend_base_url, "outcome": "completed",
                "concurrent_users": result["concurrent_users"],
                "avg_response_time_ms": result["avg_response_time_ms"],
                "p95_response_time_ms": result["p95_response_time_ms"],
                "failed_request_rate": result["failed_request_rate"],
                "severity": severity,
            })
        else:
            evidence.append({
                "todo_type": "performance_check", "check": "load_test",
                "url": backend_base_url, "outcome": result["status"],
                "detail": result.get("reason") or result.get("detail"),
                "requires_confirmation": result.get("requires_confirmation", False),
            })

    return evidence
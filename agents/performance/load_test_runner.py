"""
Wraps k6 for API load testing. Every load test plan is validated against
Budget Enforcer BEFORE k6 ever runs - this is the module where Phase 0's
resource_limits.py and cost_estimator.py actually matter, not just get
tested in isolation.
"""
import subprocess
import json
import tempfile
import os
from core.budget.budget_enforcer import evaluate_load_test_plan


K6_SCRIPT_TEMPLATE = """
import http from 'k6/http';
import {{ sleep, check }} from 'k6';

export const options = {{
    vus: {vus},
    duration: '{duration}s',
}};

export default function () {{
    const res = http.get('{url}');
    check(res, {{ 'status is not 5xx': (r) => r.status < 500 }});
    sleep(1);
}}
"""


def run_load_test(url: str, tier: str, concurrent_users: int, duration_seconds: int,
                    developer_confirmed: bool = False) -> dict:
    """
    Every call passes through Budget Enforcer first. A blocked/needs-confirmation
    decision means k6 never runs - no exceptions, no bypass, regardless of
    who calls this function or what agent requests it.
    """
    decision = evaluate_load_test_plan(tier, concurrent_users, duration_seconds, developer_confirmed)

    if not decision.allowed:
        return {
            "status": "blocked",
            "reason": decision.reason,
            "requires_confirmation": decision.requires_confirmation,
            "estimate": decision.estimate,
        }

    script_path = os.path.join(tempfile.gettempdir(), f"k6_script_{abs(hash(url))}.js")
    with open(script_path, "w") as f:
        f.write(K6_SCRIPT_TEMPLATE.format(vus=concurrent_users, duration=duration_seconds, url=url))

    try:
        result = subprocess.run(
            ["k6", "run", "--summary-export", script_path.replace(".js", "_summary.json"), script_path],
            capture_output=True, text=True, timeout=duration_seconds + 30 , shell=True
        )

        summary_path = script_path.replace(".js", "_summary.json")
        if not os.path.exists(summary_path):
            return {"status": "failed", "detail": result.stdout[-500:] + result.stderr[-500:]}

        with open(summary_path, "r") as f:
            summary = json.load(f)

        os.remove(script_path)
        os.remove(summary_path)

        metrics = summary.get("metrics", {})
        http_req_duration = metrics.get("http_req_duration", {})
        http_req_failed = metrics.get("http_req_failed", {})

        return {
            "status": "completed",
            "concurrent_users": concurrent_users,
            "duration_seconds": duration_seconds,
            "avg_response_time_ms": http_req_duration.get("avg"),
            "p95_response_time_ms": http_req_duration.get("p(95)"),
            "max_response_time_ms": http_req_duration.get("max"),
            "failed_request_rate": http_req_failed.get("rate", 0),
            "total_requests": metrics.get("http_reqs", {}).get("count"),
        }

    except subprocess.TimeoutExpired:
        return {"status": "timeout", "detail": f"Load test exceeded time limit"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:300]}
    finally:
        if os.path.exists(script_path):
            try:
                os.remove(script_path)
            except Exception:
                pass
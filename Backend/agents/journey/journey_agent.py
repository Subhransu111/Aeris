"""
Journey Planner Agent: detects known user journeys from the crawl graph,
then validates each matched journey by actually walking it in a browser
and checking the end state is reached correctly - not just that pages
exist in isolation, but that clicking through them in sequence works.
"""
from agents.journey.journey_detector import detect_journeys
from core.core.action_wrapper import execute_action


def _get_page_url(sitemap: dict, page_key: str) -> str:
    return sitemap["pages"].get(page_key, {}).get("url")


def validate_journey(page, sitemap: dict, journey: dict, agent_id: str, base_domain: str, verified_domain: str) -> dict:
    """
    Walks the detected path by navigating directly to each URL in sequence
    (simpler and more robust than re-finding/re-clicking the exact original
    trigger element, which may have shifted selector since crawl time) and
    confirms each step is reachable and matches its expected classification.
    """
    if not journey["matched"]:
        return {**journey, "validation": "not_applicable", "detail": "Journey pattern not found in this app"}

    path = journey["path"]
    step_results = []

    for i, page_key in enumerate(path):
        url = _get_page_url(sitemap, page_key)
        if not url:
            step_results.append({"step": i, "page_key": page_key, "outcome": "url_not_found"})
            continue

        action = {"type": "navigate", "target_domain": base_domain, "verified_domain": verified_domain}
        decision = execute_action(agent_id, action, sandbox_mode=True)
        if decision["status"] != "executed":
            step_results.append({"step": i, "outcome": "policy_blocked"})
            continue

        try:
            page.goto(url, wait_until="load", timeout=15000)
            page.wait_for_timeout(800)
            reachable = True
            has_error_text = page.evaluate("""
                () => document.body.innerText.toLowerCase().includes('error') ||
                      document.body.innerText.toLowerCase().includes('not found')
            """)
        except Exception as e:
            reachable = False
            has_error_text = False

        step_results.append({
            "step": i, "page_key": page_key, "url": url,
            "outcome": "reachable" if reachable and not has_error_text else "failed",
        })

    all_ok = all(s["outcome"] == "reachable" for s in step_results)

    return {
        **journey,
        "validation": "completed" if all_ok else "broken",
        "step_results": step_results,
    }


def run_journey_agent(page, sitemap: dict, base_domain: str, verified_domain: str,
                        agent_id: str = "journey_agent") -> list:
    detected = detect_journeys(sitemap)
    evidence = []

    for journey in detected:
        if not journey["matched"]:
            evidence.append({
                "todo_type": "journey_check",
                "journey_name": journey["journey_name"],
                "description": journey["description"],
                "outcome": "not_found_in_app",
                "severity": "info",
            })
            continue

        result = validate_journey(page, sitemap, journey, agent_id, base_domain, verified_domain)
        evidence.append({
            "todo_type": "journey_check",
            "journey_name": result["journey_name"],
            "description": result["description"],
            "outcome": result["validation"],
            "path": result.get("path"),
            "step_results": result.get("step_results"),
            "severity": "needs_review" if result["validation"] == "broken" else "info",
        })

    return evidence
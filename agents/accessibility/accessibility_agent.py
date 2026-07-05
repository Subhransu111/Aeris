"""
Accessibility Agent: runs axe-core against each crawled page to detect
WCAG violations. Reuses the same page object from site_explorer's crawl --
no separate browser session needed, since axe-core is just injected JS
that runs against whatever page is currently loaded.
"""
import json
import os

AXE_CORE_PATH = os.path.join(os.path.dirname(__file__), "axe.min.js")


def _load_axe_script() -> str:
    with open(AXE_CORE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def run_accessibility_check(page) -> dict:
    """
    Injects axe-core into the currently loaded page and runs its audit.
    Returns a summary dict: violations grouped by impact level, plus
    full raw results for detailed reporting later.
    """
    try:
        axe_script = _load_axe_script()
        page.evaluate(axe_script)
        results = page.evaluate("""
            () => new Promise((resolve) => {
                axe.run(document, {}, (err, results) => {
                    if (err) resolve({ error: err.message });
                    else resolve(results);
                });
            })
        """)
    except Exception as e:
        return {"status": "error", "detail": str(e)[:300]}

    if "error" in results:
        return {"status": "error", "detail": results["error"]}

    violations = results.get("violations", [])
    by_impact = {"critical": [], "serious": [], "moderate": [], "minor": []}

    for v in violations:
        impact = v.get("impact", "minor")
        by_impact.setdefault(impact, []).append({
            "id": v.get("id"),
            "description": v.get("description"),
            "help": v.get("help"),
            "help_url": v.get("helpUrl"),
            "nodes_affected": len(v.get("nodes", [])),
            "sample_selector": v["nodes"][0]["target"][0] if v.get("nodes") else None,
        })

    return {
        "status": "completed",
        "total_violations": len(violations),
        "by_impact": by_impact,
        "passes_count": len(results.get("passes", [])),
    }


def run_accessibility_agent(sitemap: dict, page) -> list:
    """
    Walks pages already discovered by site_explorer, re-visits each one
    (fresh navigation, since the crawl's page object has moved on), and
    runs the accessibility check. Returns evidence records in the same
    shape convention as functional_agent.py for consistent storage.
    """
    evidence = []

    for page_key, page_data in sitemap["pages"].items():
        if not page_data.get("reachable"):
            continue

        url = page_data.get("url")
        try:
            page.goto(url, wait_until="load", timeout=15000)
            page.wait_for_timeout(1000)
        except Exception as e:
            evidence.append({
                "todo_type": "accessibility_check", "url": url,
                "outcome": "navigation_failed", "detail": str(e)[:200],
            })
            continue

        result = run_accessibility_check(page)

        if result["status"] == "error":
            evidence.append({
                "todo_type": "accessibility_check", "url": url,
                "outcome": "check_failed", "detail": result["detail"],
            })
            continue

        evidence.append({
            "todo_type": "accessibility_check",
            "url": url,
            "auth_state": page_data.get("auth_state"),
            "outcome": "completed",
            "total_violations": result["total_violations"],
            "critical_count": len(result["by_impact"]["critical"]),
            "serious_count": len(result["by_impact"]["serious"]),
            "moderate_count": len(result["by_impact"]["moderate"]),
            "minor_count": len(result["by_impact"]["minor"]),
            "violations_detail": result["by_impact"],
            "severity": "needs_review" if result["by_impact"]["critical"] or result["by_impact"]["serious"] else "low",
        })

    return evidence
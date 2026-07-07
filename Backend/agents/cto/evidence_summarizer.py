"""
Condenses raw evidence records into a compact summary suitable for a
single LLM call. Raw evidence can run into hundreds of records (headers
repeated per page, etc.) - this deduplicates and aggregates before
handing anything to the model, keeping token cost low and signal high.
"""
from collections import defaultdict


def summarize_evidence(all_evidence: dict) -> dict:
    """all_evidence: {"functional": [...], "accessibility": [...], "security": [...], "performance": [...]}"""
    summary = {
        "functional": _summarize_functional(all_evidence.get("functional", [])),
        "accessibility": _summarize_accessibility(all_evidence.get("accessibility", [])),
        "security": _summarize_security(all_evidence.get("security", [])),
        "performance": _summarize_performance(all_evidence.get("performance", [])),
    }
    return summary


def _summarize_functional(records: list) -> dict:
    total = len(records)
    by_outcome = defaultdict(int)
    concerns = []

    for r in records:
        outcome = r.get("outcome", r.get("todo_type"))
        by_outcome[outcome] += 1
        if r.get("outcome") == "executed" and r.get("result_type") == "no_visible_change" and r.get("expect") == "validation_error":
            concerns.append(f"{r.get('form_type')} form at {r.get('url')}: '{r.get('case_name')}' showed no visible validation response")
        if r.get("todo_type") == "access_control_check":
            concerns.append(f"Access control: {r.get('note')} at {r.get('url')}")

    return {"total_tests": total, "outcome_breakdown": dict(by_outcome), "concerns": list(set(concerns))[:10]}


def _summarize_accessibility(records: list) -> dict:
    total_critical = sum(r.get("critical_count", 0) for r in records)
    total_serious = sum(r.get("serious_count", 0) for r in records)
    total_moderate = sum(r.get("moderate_count", 0) for r in records)

    violation_types = defaultdict(int)
    for r in records:
        for severity_list in r.get("violations_detail", {}).values():
            for v in severity_list:
                violation_types[v.get("id")] += v.get("nodes_affected", 1)

    return {
        "pages_checked": len(records),
        "total_critical": total_critical, "total_serious": total_serious, "total_moderate": total_moderate,
        "most_common_violations": sorted(violation_types.items(), key=lambda x: -x[1])[:5],
    }


def _summarize_security(records: list) -> dict:
    by_check = defaultdict(lambda: {"count": 0, "severity": "info", "urls": set()})

    for r in records:
        check = r.get("check", "unknown")
        entry = by_check[check]
        entry["count"] += 1
        if r.get("severity") in ("critical", "high") or (r.get("outcome") == "vulnerable" and entry["severity"] not in ("critical", "high")):
            entry["severity"] = r.get("severity", "moderate")
        entry["urls"].add(r.get("url", ""))

    findings = []
    for check, data in by_check.items():
        if data["severity"] in ("critical", "high", "moderate") and any(
            r.get("check") == check and r.get("outcome") == "vulnerable" for r in records
        ):
            findings.append({
                "check": check, "severity": data["severity"],
                "occurrences": data["count"], "affected_urls": list(data["urls"])[:3],
            })

    return {"total_checks_run": len(records), "vulnerable_findings": findings}


def _summarize_performance(records: list) -> dict:
    lighthouse_records = [r for r in records if r.get("check") == "lighthouse" and r.get("outcome") == "completed"]
    load_test_records = [r for r in records if r.get("check") == "load_test"]

    avg_score = sum(r["performance_score"] for r in lighthouse_records) / len(lighthouse_records) if lighthouse_records else None
    worst_page = min(lighthouse_records, key=lambda r: r["performance_score"], default=None)

    all_opportunities = defaultdict(int)
    for r in lighthouse_records:
        for opp in r.get("opportunities", []):
            all_opportunities[opp["title"]] += 1

    return {
        "pages_tested": len(lighthouse_records),
        "average_performance_score": round(avg_score) if avg_score else None,
        "worst_page": {"url": worst_page["url"], "score": worst_page["performance_score"]} if worst_page else None,
        "common_opportunities": sorted(all_opportunities.items(), key=lambda x: -x[1])[:5],
        "load_test_results": [
            {"url": r.get("url"), "outcome": r.get("outcome"), "avg_response_ms": r.get("avg_response_time_ms"),
             "failed_rate": r.get("failed_request_rate")}
            for r in load_test_records
        ],
    }
def build_run_metadata(sitemap: dict, all_evidence: dict, app_name: str,
                         frontend_framework: str = None, backend_framework: str = None,
                         database: str = None) -> dict:
    """
    Grounds the LLM's reasoning in actual coverage facts, not just findings -
    lets it note things like 'only 3 of 7 forms were tested' rather than
    speaking as if everything was checked equally.
    """
    pages = sitemap.get("pages", {})
    authenticated_pages = [p for p in pages.values() if p.get("auth_state") not in ("anonymous", None)]
    all_forms = [f for p in pages.values() for f in p.get("forms", [])]

    functional_tested_urls = set(r.get("url") for r in all_evidence.get("functional", []) if r.get("todo_type") == "form_test")

    return {
        "application_name": app_name,
        "frontend_framework": frontend_framework,
        "backend_framework": backend_framework,
        "database": database,
        "pages_discovered": len(pages),
        "authenticated_pages_reached": len(authenticated_pages),
        "forms_discovered": len(all_forms),
        "forms_functionally_tested": len(functional_tested_urls),
        "api_endpoints_discovered": len(sitemap.get("api_endpoints", [])),
        "third_party_auth_detected": any(
            e.get("third_party_auth") for p in pages.values() for e in p.get("interaction_edges", [])
        ),
    }
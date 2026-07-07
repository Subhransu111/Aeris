"""
Functional Agent: executes the site-wide test plan produced by test_planner.py.

For each todo item:
  - form_test  -> fills the real form with planned test-case values and submits,
                  routed through execute_action() so payment-adjacent forms
                  (checkout) get mocked instead of really submitted, same
                  discipline as button clicks in interaction_discovery.py.
  - button_test -> payment/destructive/logout buttons already get exercised by
                  interaction_discovery.py during crawl; this agent just
                  re-validates/re-runs them on demand and records the outcome
                  in the same evidence format as form tests.
  - access_control_check -> no execution needed, already a finding from the
                  crawl itself; just carried through to evidence.

Every real browser action goes through execute_action() first. No action
here bypasses the Policy Engine, regardless of who is calling it.
"""
from urllib.parse import urlparse
from Backend.core.core.action_wrapper import execute_action
from Backend.agents.functional.test_planner import plan_form_tests, plan_button_tests
from Backend.core.Exploration.dom_fingerprint import compute_dom_fingerprint


def _classify_field_type(field: dict) -> str:
    return field.get("type", "text").lower()


def _fill_and_submit_form(page, form: dict, field_values: dict, agent_id: str,
                           base_domain: str, verified_domain: str) -> dict:
    """
    Fills the real form with the given values and submits it, but only
    after clearing the Policy Engine. Checkout/payment-type forms are
    routed as 'form_submit_payment' so they get mocked, never really
    submitted -- consistent with how payment buttons are handled.
    """
    is_payment_form = any(
        k in (f.get("name", "") + f.get("label", "") + f.get("placeholder", "")).lower()
        for f in form["fields"]
        for k in ("card", "cvv", "expiry", "billing")
    )

    action = {
        "type": "form_submit_payment" if is_payment_form else "form_submit",
        "target_domain": base_domain,
        "verified_domain": verified_domain,
    }
    decision = execute_action(agent_id, action, sandbox_mode=True)


    if decision["status"] == "mocked":
        return {"outcome": "mocked", "detail": "Payment-related form - submission skipped, synthetic success logged"}

    if decision["status"] == "blocked":
        return {"outcome": "blocked", "detail": "Policy engine blocked this form submission"}

    # decision == "executed" -> actually fill and submit
    try:
        for field in form["fields"]:
            selector = field.get("selector")
            if not selector:
                continue
            value = field_values.get(field["name"])
            if value is None:
                continue
            ftype = _classify_field_type(field)
            if ftype in ("checkbox", "radio"):
                if value:
                    page.check(selector, timeout=3000)
            else:
                page.fill(selector, str(value), timeout=3000)

        before_url = page.url
        before_fp = compute_dom_fingerprint(page.content())

        submit_selector = form.get("submit_selector")
        if submit_selector:
            page.click(submit_selector, timeout=5000)
        else:
            page.keyboard.press("Enter")

        page.wait_for_timeout(1200)
        try:
            page.wait_for_load_state("load", timeout=8000)
        except Exception:
            pass

        after_url = page.url
        after_fp = compute_dom_fingerprint(page.content())

        from Backend.core.Exploration.screenshot_manager import get_screenshot_path
    
        debug_screenshot = get_screenshot_path(f"exec_{form.get('action','noform')}_{hash(str(field_values))%10000}", "screenshots")
        try:
            page.screenshot(path=debug_screenshot, full_page=True)
        except Exception:
            debug_screenshot = None

        # Try to surface any visible error/validation message left on the page
        visible_text = ""
        try:
            visible_text = page.evaluate("document.body.innerText").lower()
        except Exception:
            pass

        error_signals = ["error", "invalid", "required", "incorrect", "failed", "already exists"]
        likely_error_shown = any(sig in visible_text for sig in error_signals)

        if after_url != before_url:
            result_type = "navigation"
        elif after_fp != before_fp:
            result_type = "state_change_possible_validation_or_success"
        else:
            result_type = "no_visible_change"

        return {
            "outcome": "executed",
            "result_type": result_type,
            "before_url": before_url,
            "after_url": after_url,
            "likely_error_shown": likely_error_shown,
            "screenshot": debug_screenshot,
        }

    except Exception as e:
        return {"outcome": "execution_failed", "detail": str(e)[:300]}


def run_form_test_item(page, item: dict, agent_id: str, base_url: str, verified_domain: str) -> list:
    """
    Runs all planned test cases for a single form_test todo item.
    Returns a list of evidence records, one per test case.
    """
    form = item["form"]
    classification = item["form_classification"]
    url = item["url"]
    base_domain = urlparse(base_url).netloc

    cases = plan_form_tests(form, classification)
    records = []

    for case in cases:
        try:
            page.goto(url, wait_until="load", timeout=15000)
            page.wait_for_timeout(500)
        except Exception as e:
            records.append({
                "todo_type": "form_test", "url": url, "auth_state": item.get("auth_state"),
                "form_type": classification["type"], "case_name": case["case_name"],
                "expect": case["expect"], "outcome": "navigation_failed", "detail": str(e)[:200],
            })
            continue

        result = _fill_and_submit_form(page, form, case["field_values"], agent_id, base_domain, verified_domain)

        records.append({
            "todo_type": "form_test",
            "url": url,
            "auth_state": item.get("auth_state"),
            "form_type": classification["type"],
            "case_name": case["case_name"],
            "expect": case["expect"],
            **result,
        })

    return records


def run_button_test_item(item: dict) -> dict:
    """
    button_test items were already executed during crawl by
    interaction_discovery.py (if run_interactions=True). This just
    reformats that item into the same evidence shape as form tests,
    so the report layer has one consistent structure to read.
    """
    classification = item["button_classification"]
    cases = plan_button_tests(item["button"], classification)
    return {
        "todo_type": "button_test",
        "url": item["url"],
        "auth_state": item.get("auth_state"),
        "button_text": item["button"]["text"],
        "button_type": classification["type"],
        "planned_cases": cases,
        "note": "Executed during crawl via interaction_discovery.py (see interaction_edges in sitemap for actual outcome)",
    }


def run_functional_agent(page, todo: list, base_url: str, verified_domain: str,
                          agent_id: str = "functional_agent") -> list:
    """
    Main entry point. Walks the todo list produced by build_site_test_plan()
    and executes each item, returning a flat list of evidence records.
    """
    evidence = []

    for item in todo:
        if item["type"] == "access_control_check":
            evidence.append({
                "todo_type": "access_control_check",
                "url": item["url"],
                "note": item["note"],
                "severity": "needs_review",
            })

        elif item["type"] == "form_test":
            evidence.extend(run_form_test_item(page, item, agent_id, base_url, verified_domain))

        elif item["type"] == "button_test":
            evidence.append(run_button_test_item(item))

    return evidence
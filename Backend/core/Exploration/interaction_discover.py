from urllib.parse import urlparse
from Backend.core.Exploration.dom_fingerprint import compute_dom_fingerprint
from Backend.core.core.action_wrapper import execute_action
from Backend.agents.functional.element_classifier import classify_button


def discover_interactions(page, base_url: str, base_domain: str, candidates: list,
                           max_interactions: int = 25, agent_id: str = "functional_agent",
                           verified_domain: str = None) -> list:
    """
    Clicks every candidate with no resolvable href and observes the result.
    Only payment-completion actions are held back (mocked); everything else
    (including destructive actions like delete/logout) executes for real,
    since this only ever runs inside the sandbox.
    """
    edges = []
    to_test = [c for c in candidates if not c.get("href")][:max_interactions]
    verified_domain = verified_domain or base_domain

    for cand in to_test:
        classification = classify_button({"text": cand["text"]})

        action = {
            "type": "ui_click_payment" if classification["type"] == "payment_action" else "ui_click",
            "target_domain": base_domain,
            "verified_domain": verified_domain,
        }
        decision = execute_action(agent_id, action, sandbox_mode=True)

        if decision["status"] == "mocked":
            edges.append({
                "trigger_text": cand["text"],
                "trigger_selector": cand["selector"],
                "result_type": "payment_mocked",
                "result": "Payment action detected — click skipped, synthetic success logged",
                "classification": classification["type"],
            })
            continue

        if decision["status"] == "blocked":
            edges.append({
                "trigger_text": cand["text"],
                "trigger_selector": cand["selector"],
                "result_type": "policy_blocked",
                "result": None,
                "classification": classification["type"],
            })
            continue

        # decision == "executed" -> proceed with real click
        try:
            page.goto(base_url, wait_until="load", timeout=15000)
            page.wait_for_timeout(500)
        except Exception:
            continue

        try:
            before_url = page.url
            before_fp = compute_dom_fingerprint(page.content())

            page.locator(cand["selector"]).scroll_into_view_if_needed(timeout=3000)
            page.click(cand["selector"], timeout=5000)
            page.wait_for_timeout(800)

            after_url = page.url
            after_fp = compute_dom_fingerprint(page.content())
        except Exception as e:
            edges.append({
                "trigger_text": cand["text"],
                "trigger_selector": cand["selector"],
                "result_type": "click_failed",
                "result": str(e)[:200],
                "classification": classification["type"],
            })
            continue

        if after_url != before_url:
            same_origin = urlparse(after_url).netloc == base_domain
            edges.append({
                "trigger_text": cand["text"],
                "trigger_selector": cand["selector"],
                "result_type": "navigation" if same_origin else "external_navigation",
                "result": after_url,
                "classification": classification["type"],
            })
        elif after_fp != before_fp:
            edges.append({
                "trigger_text": cand["text"],
                "trigger_selector": cand["selector"],
                "result_type": "state_change",
                "result": after_fp,
                "classification": classification["type"],
            })
        else:
            # Check console for errors that might explain a silent click
            try:
                has_error = page.evaluate("window.__aegisHadError || false")
            except Exception:
                has_error = False
            edges.append({
                "trigger_text": cand["text"], "trigger_selector": cand["selector"],
                "result_type": "no_visible_change", "result": None,
                "classification": classification["type"],
                "possible_js_error": has_error,
            })

    return edges
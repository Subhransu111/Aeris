"""
Detects and expands collapsed UI (accordions, tabs, "read more" toggles)
so their content becomes visible to static extraction. Distinct from
modal_handler.py (which dismisses blocking overlays) -- this expands
in-page content that would otherwise be invisible to the crawler.

Uses the same click-and-observe pattern as interaction_discovery.py but
targets a different candidate set: ARIA accordion/tab roles and common
class-name patterns, not every clickable element on the page.
"""
from .js_helper import GET_SELECTOR_JS
from Backend.core.core.action_wrapper import execute_action

DETECT_EXPANDABLE_JS = GET_SELECTOR_JS + """
() => {
    const selectors = [
        '[role="tab"]', '[aria-expanded="false"]', '[class*="accordion"]',
        '[class*="collapse"]', 'details:not([open]) summary', '[class*="tab-"]'
    ];
    const seen = new Set();
    const results = [];
    document.querySelectorAll(selectors.join(',')).forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        const sel = getSelector(el);
        if (seen.has(sel)) return;
        seen.add(sel);
        const text = (el.innerText || '').trim().slice(0, 60);
        results.push({ selector: sel, text });
    });
    return results;
}
"""


def expand_collapsed_content(page, agent_id: str = "explorer", max_expansions: int = 10) -> list:
    """
    Clicks accordion/tab/details elements to reveal hidden content.
    Routed through policy engine like all other clicks for consistency,
    though these are near-universally safe (ui_click -> allow).
    """
    try:
        candidates = page.evaluate(DETECT_EXPANDABLE_JS)
    except Exception:
        return []

    expanded = []
    for cand in candidates[:max_expansions]:
        decision = execute_action(agent_id, {"type": "ui_click"}, sandbox_mode=True)
        if decision["status"] == "blocked":
            continue
        try:
            page.click(cand["selector"], timeout=2000)
            page.wait_for_timeout(300)
            expanded.append(cand)
        except Exception:
            continue

    return expanded
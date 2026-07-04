"""
Detects and dismisses overlays (permission prompts, cookie banners, newsletter
popups) that sit on top of the real page. Left unhandled, these block every
element behind them from being meaningfully tested, and on many SPAs the page
body doesn't even finish mounting until the overlay is dismissed.

Dismissal preference order matters: we prefer the negative/neutral option
("Not now", "Skip") over the affirmative one ("Allow", "Accept") wherever
both are visible, since clicking "Allow" can trigger real side effects
(granting a browser geolocation permission, subscribing to a newsletter,
accepting cookies in a way that changes site behavior). We only fall back
to the affirmative option if no negative one is present, since some modals
are genuinely un-skippable gates.
"""
from core.Exploration.js_helper import GET_SELECTOR_JS

NEGATIVE_PATTERNS = ["not now", "no thanks", "maybe later", "skip", "later", "cancel"]
NEUTRAL_CLOSE_PATTERNS = ["close", "dismiss", "×", "x", "got it", "ok"]
AFFIRMATIVE_PATTERNS = ["accept", "allow", "i understand", "continue", "agree"]

DETECT_JS = """
() => {
    """ + GET_SELECTOR_JS + """

    const candidates = Array.from(document.querySelectorAll(
        'button, a, [role="button"], [class*="btn"], [class*="close"], [class*="modal"] *'
    ));
    const vw = window.innerWidth, vh = window.innerHeight;
    const results = [];
    for (const el of candidates) {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        if (rect.top < -10 || rect.top > vh || rect.left < -10 || rect.left > vw) continue;
        const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().toLowerCase();
        if (!text || text.length > 40) continue;
        results.push({ selector: getSelector(el), text });
    }
    return results;
}
"""


def _pick_match(candidates, patterns):
    for c in candidates:
        if any(p in c["text"] for p in patterns):
            return c
    return None


def dismiss_overlays(page, max_rounds: int = 4) -> list:
    """
    Repeatedly looks for and clicks dismiss-language elements. Returns a log
    of what was clicked -- worth keeping, since "how the site gates entry"
    (cookie consent, location prompt, age-gate) is itself a testable feature.
    """
    dismissed_log = []
    for _ in range(max_rounds):
        try:
            candidates = page.evaluate(DETECT_JS)
        except Exception:
            break

        match = (
            _pick_match(candidates, NEGATIVE_PATTERNS)
            or _pick_match(candidates, NEUTRAL_CLOSE_PATTERNS)
            or _pick_match(candidates, AFFIRMATIVE_PATTERNS)
        )
        if not match:
            break

        try:
            page.click(match["selector"], timeout=2000)
            page.wait_for_timeout(400)
            dismissed_log.append(match)
        except Exception:
            break

    return dismissed_log
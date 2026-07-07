"""
Detects conditions that make automated provisioning impossible or
inappropriate to keep retrying against: CAPTCHA and third-party OAuth-only
signup. Checked once per page load, before attempting to fill anything.
"""

CAPTCHA_SIGNATURES = ["recaptcha", "g-recaptcha", "h-captcha", "hcaptcha", "cf-turnstile", "turnstile"]
OAUTH_ONLY_SIGNATURES = ["continue with google", "continue with github", "continue with apple", "sign in with google"]


def detect_blocker(page) -> dict:
    """Returns {"blocked": bool, "reason": str} - caller should stop immediately if blocked."""
    try:
        html = page.content().lower()
    except Exception:
        return {"blocked": False, "reason": None}

    for sig in CAPTCHA_SIGNATURES:
        if sig in html:
            return {"blocked": True, "reason": f"CAPTCHA detected ({sig}) - automated provisioning not possible"}

    try:
        body_text = page.evaluate("document.body.innerText").lower()
    except Exception:
        body_text = ""

    has_oauth_button = any(sig in body_text for sig in OAUTH_ONLY_SIGNATURES)
    try:
        has_own_form = page.evaluate("document.querySelectorAll('form input[type=password]').length > 0")
    except Exception:
        has_own_form = True  # assume yes if we can't check, avoid false-blocking

    if has_oauth_button and not has_own_form:
        return {"blocked": True, "reason": "Signup only available via third-party OAuth - not testable without pre-registered callback URL"}

    return {"blocked": False, "reason": None}
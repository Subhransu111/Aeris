"""
Multi-signal success detection - a single signal (URL change, keyword
match) is unreliable since intermediate steps (verify-email, OTP,
complete-profile) also change the URL/DOM without meaning registration
succeeded. Combines several signals for a much more reliable verdict.
"""

def detect_registration_success(page, original_url: str) -> dict:
    signals = {}

    try:
        signals["url_changed"] = page.url.rstrip("/") != original_url.rstrip("/")
    except Exception:
        signals["url_changed"] = False

    try:
        body_text = page.evaluate("document.body.innerText").lower()
    except Exception:
        body_text = ""

    signals["has_validation_error"] = any(k in body_text for k in
        ("error", "invalid", "required", "already exists", "failed", "incorrect"))

    signals["has_logout_control"] = any(k in body_text for k in ("sign out", "log out", "logout"))
    signals["mentions_dashboard_or_welcome"] = any(k in body_text for k in ("dashboard", "welcome", "good morning", "good evening", "good afternoon"))

    try:
        signals["has_auth_cookie"] = page.evaluate("document.cookie.length > 0")
    except Exception:
        signals["has_auth_cookie"] = False

    try:
        signals["has_local_storage_token"] = page.evaluate("""
            () => {
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i).toLowerCase();
                    if (key.includes('token') || key.includes('auth') || key.includes('session')) return true;
                }
                return false;
            }
        """)
    except Exception:
        signals["has_local_storage_token"] = False

    # Known non-terminal intermediate steps - if URL/text matches these,
    # this is NOT success yet, regardless of other signals.
    intermediate_markers = ["verify-email", "verify email", "otp", "complete-profile", "complete your profile", "confirm your email"]
    signals["is_intermediate_step"] = any(m in page.url.lower() or m in body_text for m in intermediate_markers)

    if signals["is_intermediate_step"]:
        return {"success": False, "reason": "intermediate_step_detected", "signals": signals}

    if signals["has_validation_error"]:
        return {"success": False, "reason": "validation_error_present", "signals": signals}

    positive_signals = sum([
        signals["url_changed"],
        signals["has_logout_control"],
        signals["mentions_dashboard_or_welcome"],
        signals["has_auth_cookie"],
        signals["has_local_storage_token"],
    ])

    # Require at least 2 corroborating positive signals, not just one -
    # this is the core fix for the original single-signal weakness.
    success = positive_signals >= 2
    return {"success": success, "reason": "multi_signal_match" if success else "insufficient_signals", "signals": signals}
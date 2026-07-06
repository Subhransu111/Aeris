import re

ADJUSTMENT_RULES = [
    (r"special character", lambda ctx: ctx.update({"password": ctx.get("password", "AegisTest") + "!"}) or "password"),
    (r"password.*(?:8|eight).*character", lambda ctx: ctx.update({"password": (ctx.get("password") or "") + "Xy9!"}) or "password"),
    (r"uppercase", lambda ctx: ctx.update({"password": "A" + ctx.get("password", "aegistest123!")}) or "password"),
    (r"lowercase", lambda ctx: ctx.update({"password": ctx.get("password", "AEGISTEST123!") + "x"}) or "password"),
    (r"password.*(?:number|digit)", lambda ctx: ctx.update({"password": ctx.get("password", "AegisTest!") + "9"}) or "password"),
]

# Terminal errors: retrying won't help, caller should stop and report, not loop
TERMINAL_ERROR_PATTERNS = {
    "already exists": "account_already_exists",
    "already registered": "account_already_exists",
    "too many requests": "rate_limited",
    "captcha": "captcha_required",
    "invalid otp": "otp_required",
    "username unavailable": "username_taken",
    "agreement": "terms_not_accepted",
}

REQUIRED_FIELD_PATTERN = re.compile(r"[\`'\"]?([\w\.]+)[\`'\"]?\s+(?:is required|cannot be (?:empty|blank))", re.IGNORECASE)


def check_terminal_error(error_text: str) -> str:
    """Returns a reason string if the error is unrecoverable by retrying, else None."""
    error_lower = error_text.lower()
    for pattern, reason in TERMINAL_ERROR_PATTERNS.items():
        if pattern in error_lower:
            return reason
    return None


def parse_error_for_adjustment(error_text: str, context: dict) -> str:
    error_lower = error_text.lower()
    for pattern, action in ADJUSTMENT_RULES:
        if re.search(pattern, error_lower):
            return action(context)
    return None


def find_required_field_from_error(error_text: str) -> str:
    match = REQUIRED_FIELD_PATTERN.search(error_text)
    if match:
        return match.group(1).split(".")[-1]
    return None
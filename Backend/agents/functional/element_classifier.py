# agents/functional/element_classifier.py

def classify_form(form_html: dict) -> dict:
    field_signatures = [f["type"] for f in form_html["fields"]]
    field_names = " ".join([
        f.get("name", "") + " " + f.get("label", "") + " " + f.get("placeholder", "")
        for f in form_html["fields"]
    ]).lower()
    submit_text = form_html.get("submit_button_text", "").lower()

    has_password = "password" in field_signatures
    has_identifier = (
        any(t in field_signatures for t in ["email", "tel"])
        or any(k in field_names for k in ["username", "email", "phone", "mobile"])
    )

    if has_password and has_identifier and len(form_html["fields"]) <= 4:
        if "confirm" not in field_names and "sign up" not in submit_text and "register" not in submit_text:
            return {"type": "login", "confidence": "high"}

    if has_password and ("confirm" in field_names or "sign up" in submit_text or "register" in submit_text or "create account" in submit_text):
        return {"type": "signup", "confidence": "high"}


    if "reset" in submit_text or "forgot" in field_names or "forgot" in submit_text:
        return {"type": "password_reset", "confidence": "high"}

    if len(form_html["fields"]) == 1 and form_html["fields"][0]["type"] in ("search", "text"):
        if "search" in field_names or "search" in submit_text or form_html["fields"][0]["type"] == "search":
            return {"type": "search", "confidence": "high"}

    payment_keywords = ["card", "cvv", "expiry", "billing", "payment", "checkout"]
    if any(k in field_names for k in payment_keywords) or any(k in submit_text for k in payment_keywords):
        return {"type": "checkout", "confidence": "high"}

    if "message" in field_names and "email" in field_names and not has_password:
        return {"type": "contact", "confidence": "medium"}

    if "file" in field_signatures:
        return {"type": "file_upload", "confidence": "high"}

    if len(form_html["fields"]) > 4 and not has_password:
        return {"type": "settings_update", "confidence": "medium"}

    return {"type": "unknown", "confidence": "low"}


def classify_button(button_html: dict) -> dict:
    text = button_html.get("text", "").lower()

    if any(w in text for w in [
        "buy", "purchase", "pay", "checkout", "subscribe",
         "start your subscription", "upgrade"
    ]):
        return {"type": "payment_action", "confidence": "high"}

    if any(w in text for w in ["delete", "remove"]):
        return {"type": "destructive_action", "confidence": "high"}

    if any(w in text for w in ["logout", "sign out"]):
        return {"type": "logout", "confidence": "high"}

    if any(w in text for w in ["login", "log in", "sign in", "submit", "save", "continue", "next", "register", "sign up"]):
        return {"type": "form_action", "confidence": "medium"}

    return {"type": "navigation", "confidence": "low"}
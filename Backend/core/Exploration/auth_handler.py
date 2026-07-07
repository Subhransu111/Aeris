"""
Dashboards, account pages, and admin panels don't exist to an anonymous
crawler -- they 404, redirect to /login, or just never get linked from the
public page. The only way to reach them is to actually authenticate and keep
crawling inside that session.

This module assumes test credentials are supplied by whoever configures the
platform (never guessed or brute-forced) and that extract_page_data() has
been extended to include a `selector` per form field and a `submit_selector`
per form -- without real selectors this can't reliably fill anything.
"""

LOGIN_SUCCESS_HINTS = ["logout", "log out", "sign out", "my account", "dashboard"]


def find_login_form(page_data: dict):
    """Returns the first form containing a password field, or None."""
    for form in page_data.get("forms", []):
        types = [f["type"].lower() for f in form.get("fields", [])]
        if "password" in types:
            return form
    return None


def attempt_login(page, login_form: dict, username: str, password: str) -> bool:
    console_logs = []
    page.on("console", lambda msg: console_logs.append(msg.text))

    try:
        for field in login_form.get("fields", []):
            if not field.get("selector"):
                continue
            ftype = field["type"].lower()
            if ftype == "password":
                page.fill(field["selector"], password)
            elif ftype in ("email", "text", "tel") and username:
                page.fill(field["selector"], username)

        # Verify what actually got typed, before submitting
        for field in login_form.get("fields", []):
            if field.get("selector"):
                val = page.input_value(field["selector"])
                print(f"[DEBUG] Field {field['name']} ({field['type']}) contains: '{val}'")

        if login_form.get("submit_selector"):
            page.click(login_form["submit_selector"])
        else:
            page.keyboard.press("Enter")

        page.wait_for_timeout(1500)
        page.wait_for_load_state("load", timeout=10000)

        page.screenshot(path="debug_after_login.png", full_page=True)
        print(f"[DEBUG] URL after login attempt: {page.url}")
        print(f"[DEBUG] Console messages: {console_logs}")
        body_text = page.evaluate("document.body.innerText")
        print(f"[DEBUG] Page text snippet: {body_text[:300]}")

    except Exception as e:
        print(f"[DEBUG] Login exception: {e}")
        return False

    return verify_login_success(page)


def verify_login_success(page) -> bool:
    """
    Heuristic check -- looks for the kind of chrome that only appears once
    logged in. Not foolproof, so the caller should treat a False here as
    "unverified" rather than fatal, and optionally accept an explicit
    success_url_pattern from config instead.
    """
    try:
        body_text = page.evaluate("document.body.innerText").lower()
    except Exception:
        return False
    return any(hint in body_text for hint in LOGIN_SUCCESS_HINTS)
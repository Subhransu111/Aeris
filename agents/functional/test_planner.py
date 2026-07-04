"""
Given a classified form or button, decide what test cases to run against it.
Rule-based: maps element type -> list of test case definitions. No LLM,
no guessing -- every test case here is a deterministic, well-known QA
pattern (boundary values, required-field omission, invalid formats).
"""

def plan_form_tests(form: dict, classification: dict) -> list:
    """
    Returns list of test cases: {case_name, field_values, expect}
    field_values: {field_name: value_to_enter}
    expect: rough expectation for later result comparison (not enforced here,
    just documented intent for the report layer)
    """
    form_type = classification["type"]
    fields = form["fields"]
    cases = []

    # Universal case: submit with all fields empty (should fail validation
    # if any field is required; should succeed if genuinely optional)
    required_fields = [f["name"] for f in fields if f.get("required")]
    if required_fields:
        cases.append({
            "case_name": "empty_required_fields",
            "field_values": {},
            "expect": "validation_error"
        })

    if form_type == "login":
        cases.append({"case_name": "valid_format_wrong_credentials",
                       "field_values": _fill(fields, {"email": "test@example.com", "tel": "9999999999", "password": "WrongPass123"}),
                       "expect": "auth_error_not_crash"})
        cases.append({"case_name": "sql_injection_pattern",
                       "field_values": _fill(fields, {"email": "' OR '1'='1", "tel": "' OR '1'='1", "password": "' OR '1'='1"}),
                       "expect": "rejected_safely"})
        cases.append({"case_name": "xss_pattern",
                       "field_values": _fill(fields, {"email": "<script>alert(1)</script>", "tel": "<script>alert(1)</script>"}),
                       "expect": "rejected_or_escaped"})

    elif form_type == "signup":
        cases.append({"case_name": "valid_signup_data",
                       "field_values": _fill(fields, {"name": "Test User", "email": "aegis.test+{n}@example.com",
                                                       "tel": "9876543210", "password": "ValidPass123!", "confirmPassword": "ValidPass123!"}),
                       "expect": "success_or_next_step"})
        cases.append({"case_name": "mismatched_passwords",
                       "field_values": _fill(fields, {"password": "PasswordOne1!", "confirmPassword": "PasswordTwo2!"}),
                       "expect": "validation_error"})
        cases.append({"case_name": "invalid_email_format",
                       "field_values": _fill(fields, {"email": "not-an-email"}),
                       "expect": "validation_error"})
        cases.append({"case_name": "weak_password",
                       "field_values": _fill(fields, {"password": "123", "confirmPassword": "123"}),
                       "expect": "validation_error"})
        cases.append({"case_name": "boundary_long_input",
                       "field_values": _fill(fields, {"name": "A" * 500}),
                       "expect": "handled_gracefully"})

    elif form_type == "search":
        cases.append({"case_name": "empty_search",
                       "field_values": {}, "expect": "handled_gracefully"})
        cases.append({"case_name": "special_characters",
                       "field_values": _fill(fields, {"default": "!@#$%^&*()"}),
                       "expect": "handled_gracefully"})
        cases.append({"case_name": "no_results_query",
                       "field_values": _fill(fields, {"default": "zzznonexistentqueryzzz"}),
                       "expect": "empty_state_shown"})

    elif form_type == "password_reset":
        cases.append({"case_name": "valid_email_format",
                       "field_values": _fill(fields, {"email": "test@example.com"}),
                       "expect": "generic_confirmation_no_enumeration"})
        cases.append({"case_name": "nonexistent_email",
                       "field_values": _fill(fields, {"email": "definitely_not_registered_xyz@example.com"}),
                       "expect": "generic_confirmation_no_enumeration"})  # flags if response differs -> user enumeration bug

    elif form_type == "contact":
        cases.append({"case_name": "valid_message",
                       "field_values": _fill(fields, {"email": "test@example.com", "message": "Test message from Aegis"}),
                       "expect": "success"})

    elif form_type == "checkout":
        # Payment fields never get real values -- routed through policy mock at execution time
        cases.append({"case_name": "checkout_flow_mocked",
                       "field_values": {}, "expect": "mocked_no_real_charge"})

    return cases


def _fill(fields: list, value_map: dict) -> dict:
    """
    Matches value_map keys against field names/types, falls back to
    'default' key for single-field forms (e.g. search boxes).
    """
    result = {}
    for f in fields:
        name = f["name"].lower()
        ftype = f["type"].lower()
        for key, val in value_map.items():
            if key.lower() in name or key.lower() == ftype or key == "default":
                result[f["name"]] = val
                break
    return result


def plan_button_tests(button: dict, classification: dict) -> list:
    """
    Buttons already get exercised by interaction_discovery.py's click-and-observe.
    This just documents expected behavior per type for the report layer --
    no separate action needed here.
    """
    btn_type = classification["type"]
    if btn_type == "payment_action":
        return [{"case_name": "payment_button_mocked", "expect": "mocked_no_real_charge"}]
    if btn_type == "destructive_action":
        return [{"case_name": "destructive_action_confirmed_in_sandbox", "expect": "executes_safely_in_sandbox"}]
    if btn_type == "logout":
        return [{"case_name": "logout_clears_session", "expect": "session_cleared"}]
    return [{"case_name": "click_and_observe", "expect": "no_crash"}]
def build_site_test_plan(sitemap: dict) -> list:
    """
    Walks the full crawled sitemap and produces an ordered todo list of
    test items. This is the "agent decides what to test" layer -- it
    reasons over what the site actually contains, not a fixed script.
    """
    todo = []
    priority_counter = 0

    for page_key, page_data in sitemap["pages"].items():
        if not page_data.get("reachable"):
            continue

        auth_state = page_data.get("auth_state", "anonymous")
        url = page_data.get("url", page_key)

        # Security-relevant observation: is this page reachable without auth
        # when it looks like it shouldn't be? (heuristic: classified as
        # dashboard/admin/profile but auth_state is anonymous and no redirect happened)
        if page_data.get("classification") in ("dashboard", "admin", "profile") and auth_state == "anonymous":
            todo.append({
                "priority": priority_counter, "type": "access_control_check",
                "url": url, "note": "Page classified as protected but reachable anonymously - verify this is intentional"
            })
            priority_counter += 1

        for form in page_data.get("forms", []):
            from agents.functional.element_classifier import classify_form
            classification = classify_form(form)
            todo.append({
                "priority": priority_counter, "type": "form_test",
                "url": url, "auth_state": auth_state,
                "form_classification": classification, "form": form
            })
            priority_counter += 1

        for button in page_data.get("buttons", []):
            from agents.functional.element_classifier import classify_button
            classification = classify_button(button)
            if classification["type"] in ("payment_action", "destructive_action", "logout"):
                todo.append({
                    "priority": priority_counter, "type": "button_test",
                    "url": url, "auth_state": auth_state,
                    "button_classification": classification, "button": button
                })
                priority_counter += 1

    # Ordering: auth-related tests first (login must work before we trust
    # anything about protected-page behavior), then everything else.
    todo.sort(key=lambda item: (0 if item["type"] == "access_control_check" else 1, item["priority"]))
    return todo
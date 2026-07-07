"""
Generates a plausible value for any form field based on its type/name/label/
placeholder. Every generated value is stored in `context` under a
predictable key so it can be reused later for login (email/phone/username/
password) - this was a real bug in the first version where only password
was persisted.
"""
import random
import string

LOW_CONFIDENCE_THRESHOLD = 40  # fields below this confidence are left blank rather than guessed


def _random_digits(n: int) -> str:
    return "".join(random.choices(string.digits, k=n))


def _random_letters(n: int) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


def classify_field_semantic(field: dict) -> tuple:
    """Returns (semantic_type, confidence 0-100). Centralizes the keyword
    matching so both value generation and context storage use the same
    classification - avoids the earlier bug where 'name' matched 'username'."""
    ftype = (field.get("type") or "").lower()
    name = (field.get("name") or "").lower()
    label = (field.get("label") or "").lower()
    placeholder = (field.get("placeholder") or "").lower()
    combined = f"{name} {label} {placeholder}"

    if ftype == "password" or "password" in combined:
        if any(k in combined for k in ("confirm", "re-enter", "re enter", "repeat")):
            return ("password_confirm", 95)
        return ("password", 95)

    if ftype == "email" or "email" in combined:
        return ("email", 95)

    # Username checked BEFORE generic "name" match - fixes the bug where
    # "username" incorrectly matched the full-name branch.
    if "username" in combined or "user name" in combined:
        return ("username", 90)

    if ftype == "tel" or "phone" in combined or "mobile" in combined:
        return ("phone", 90)

    if "otp" in combined or "verification code" in combined:
        return ("otp", 90)

    if "invite" in combined or "referral" in combined:
        return ("referral_code", 90)

    if "pincode" in combined or "zip" in combined or "postal" in combined:
        return ("postal_code", 85)

    if "city" in combined:
        return ("city", 80)

    if "country" in combined:
        return ("country", 90)

    if "state" in combined or "province" in combined:
        return ("state", 60)  # often dynamically populated after country - lower confidence

    if "company" in combined or "organization" in combined or "office" in combined:
        return ("company", 70)

    if "street" in combined or ("address" in combined and "email" not in combined):
        return ("street_address", 75)

    if "building" in combined:
        return ("building", 70)

    if "floor" in combined:
        return ("floor", 70)

    if "terms" in combined or "agree" in combined or "accept" in combined:
        return ("terms_agreement", 90)

    if "newsletter" in combined or "marketing" in combined or "subscribe" in combined:
        return ("marketing_optin", 90)  # will be left unchecked, see generate_value_for_field

    if "remember" in combined:
        return ("remember_me", 90)

    if ftype == "number":
        return ("generic_number", 60)

    if ftype in ("checkbox",):
        return ("generic_checkbox", 50)

    if ftype in ("radio",):
        return ("generic_radio", 50)

    if ftype in ("select", "select-one"):
        return ("generic_select", 50)

    # Full name - only after username is ruled out above
    if "name" in combined:
        return ("full_name", 80)

    if not combined.strip():
        return ("unknown", 10)

    return ("generic_text", 30)


def generate_value_for_field(field: dict, context: dict) -> str:
    """
    Mutates `context` in place, storing every generated value under a
    stable key (email, phone, password, username, full_name, ...) so
    calling code can retrieve credentials afterward. Low-confidence
    fields are left blank rather than filled with a guess.
    """
    semantic, confidence = classify_field_semantic(field)

    if confidence < LOW_CONFIDENCE_THRESHOLD:
        return ""

    if semantic == "password":
        value = context.get("password") or "AegisTest@123"
        context["password"] = value
        return value

    if semantic == "password_confirm":
        return context.get("password", "AegisTest@123")

    if semantic == "email":
        value = context.get("email") or f"aegis.test.{_random_digits(6)}@example.com"
        context["email"] = value
        return value

    if semantic == "username":
        value = context.get("username") or f"aegistest{_random_digits(4)}"
        context["username"] = value
        return value

    if semantic == "phone":
        value = context.get("phone") or ("9" + _random_digits(9))
        context["phone"] = value
        return value

    if semantic == "otp":
        return ""  # cannot generate a real OTP - leave blank, caller should detect OTP flow separately

    if semantic == "referral_code":
        return ""  # optional by convention - skip unless explicitly required, handled by caller

    if semantic == "postal_code":
        value = context.get("postal_code") or "751001"
        context["postal_code"] = value
        return value

    if semantic == "city":
        value = context.get("city") or "Bhubaneswar"
        context["city"] = value
        return value

    if semantic == "country":
        value = context.get("country") or "India"
        context["country"] = value
        return value

    if semantic == "state":
        return ""  # often dynamically dependent on country - safer to skip than guess wrong

    if semantic == "company":
        value = context.get("company") or "Aegis Test Org"
        context["company"] = value
        return value

    if semantic == "street_address":
        value = context.get("street_address") or "42 Test Street"
        context["street_address"] = value
        return value

    if semantic == "building":
        return context.get("building") or "Test Building"

    if semantic == "floor":
        return context.get("floor") or "1st Floor"

    if semantic == "terms_agreement":
        return True  # safe to accept terms in a sandbox test account

    if semantic == "marketing_optin":
        return False  # do NOT opt into marketing by default - matches real user expectation

    if semantic == "remember_me":
        return False  # neutral default, doesn't affect account creation

    if semantic == "full_name":
        value = context.get("full_name") or "Aegis Test User"
        context["full_name"] = value
        return value

    if semantic == "generic_number":
        return "1"

    if semantic == "generic_checkbox":
        return False  # unknown checkboxes default to unchecked - safer than assuming opt-in

    if semantic == "generic_radio":
        return "first_safe"  # caller resolves to first non-admin-looking option

    if semantic == "generic_select":
        return "first_valid"  # caller resolves to first enabled, non-placeholder option

    if semantic == "generic_text" and confidence >= LOW_CONFIDENCE_THRESHOLD:
        return f"aegis test {_random_letters(4)}"

    return ""
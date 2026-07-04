from urllib.parse import urlparse

def classify_page(url: str, title: str, page_data: dict) -> str:
    url_lower = url.lower()
    title_lower = title.lower()

    input_types, input_names = [], []
    for f in page_data.get("forms", []):
        for field in f.get("fields", []):
            input_types.append(field["type"].lower())
            input_names.append(field["name"].lower())
    btn_text = [b["text"].lower() for b in page_data.get("buttons", [])]

    if any(k in url_lower for k in ["checkout", "cart", "basket", "pay"]) or "checkout" in title_lower:
        return "checkout"
    if any(k in url_lower for k in ["login", "signin", "auth"]) or "log in" in title_lower or "sign in" in title_lower:
        return "login"
    if "password" in input_types and any(k in input_names or k in btn_text for k in ["login", "signin", "enter"]):
        return "login"
    if any(k in url_lower for k in ["signup", "register", "join", "create-account"]):
        return "signup"
    if "password" in input_types and any(k in input_names or k in btn_text for k in ["signup", "register", "join"]):
        return "signup"
    if any(k in url_lower for k in ["search", "query=", "q="]) or "search" in title_lower:
        return "search"
    if any(k in url_lower for k in ["admin", "backend", "manage"]):
        return "admin"
    if any(k in url_lower for k in ["profile", "account", "settings"]):
        return "profile"
    if any(k in url_lower for k in ["dashboard", "home", "console"]) or "dashboard" in title_lower:
        return "dashboard"
    if urlparse(url).path in ["", "/"]:
        return "landing"
    return "informational"
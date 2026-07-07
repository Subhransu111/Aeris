"""
Known journey patterns, defined as sequences of page classifications or
keyword-matched actions. This is intentionally a starting library, not
exhaustive - matches the same rule-based philosophy as element_classifier.py.
New patterns can be added without touching the traversal engine.
"""

JOURNEY_PATTERNS = [
    {
        "name": "registration_to_dashboard",
        "description": "New user signs up and reaches their authenticated home",
        "sequence": ["landing", "signup", "dashboard"],
    },
    {
        "name": "login_to_dashboard",
        "description": "Returning user logs in and reaches their authenticated home",
        "sequence": ["landing", "login", "dashboard"],
    },
    {
        "name": "browse_to_purchase",
        "description": "User browses a product/menu and completes a purchase",
        "sequence": ["landing", "checkout"],
        "keyword_hints": ["menu", "product", "plan", "cart", "order"],
    },
    {
        "name": "password_recovery",
        "description": "User recovers access via forgot-password flow",
        "sequence": ["login"],
        "keyword_hints": ["forgot", "reset password"],
    },
    {
        "name": "profile_update",
        "description": "Authenticated user views and updates their profile",
        "sequence": ["dashboard", "profile"],
    },
]
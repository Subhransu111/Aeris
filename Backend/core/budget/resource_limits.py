TIER_LIMITS = {
    "free": {
        "max_concurrent_users": 50,
        "max_test_duration_seconds": 300,
        "max_llm_tokens_per_run": 50000,
        "max_api_calls_per_run": 500,
        "allow_chaos_engineering": False,
        "requires_confirmation_above_users": 50,
    },
    "pro": {
        "max_concurrent_users": 1000,
        "max_test_duration_seconds": 900,
        "max_llm_tokens_per_run": 300000,
        "max_api_calls_per_run": 5000,
        "allow_chaos_engineering": True,
        "requires_confirmation_above_users": 500,
    },
    "enterprise": {
        "max_concurrent_users": 10000,
        "max_test_duration_seconds": 3600,
        "max_llm_tokens_per_run": 2000000,
        "max_api_calls_per_run": 50000,
        "allow_chaos_engineering": True,
        "requires_confirmation_above_users": 2000,
    },
}

def get_limits(tier: str) -> dict:
    return TIER_LIMITS.get(tier, TIER_LIMITS["free"])
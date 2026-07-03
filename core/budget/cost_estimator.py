def estimate_load_test_cost(concurrent_users: int, duration_seconds: int) -> dict:
    """
    Rough resource estimate for a load test. Not billing-accurate —
    purpose is to flag runs that need explicit confirmation.
    """
    estimated_requests = concurrent_users * (duration_seconds / 2)  # assume 1 req/2s/user
    estimated_agent_container_mb = min(concurrent_users * 0.5, 4096)  # cap estimate display

    return {
        "concurrent_users": concurrent_users,
        "duration_seconds": duration_seconds,
        "estimated_requests": int(estimated_requests),
        "estimated_load_generator_memory_mb": int(estimated_agent_container_mb),
        "risk_level": _risk_level(concurrent_users)
    }

def _risk_level(concurrent_users: int) -> str:
    if concurrent_users <= 100:
        return "low"
    if concurrent_users <= 1000:
        return "medium"
    return "high"

def estimate_llm_cost(planned_agent_calls: int, avg_tokens_per_call: int = 2000) -> dict:
    total_tokens = planned_agent_calls * avg_tokens_per_call
    return {
        "planned_agent_calls": planned_agent_calls,
        "estimated_total_tokens": total_tokens
    }
from Backend.core.budget.resource_limits import get_limits
from Backend.core.budget.cost_estimator import estimate_load_test_cost, estimate_llm_cost

class BudgetDecision:
    def __init__(self, allowed: bool, reason: str, requires_confirmation: bool = False, estimate: dict = None):
        self.allowed = allowed
        self.reason = reason
        self.requires_confirmation = requires_confirmation
        self.estimate = estimate

    def to_dict(self):
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "requires_confirmation": self.requires_confirmation,
            "estimate": self.estimate
        }


def evaluate_load_test_plan(tier: str, concurrent_users: int, duration_seconds: int, developer_confirmed: bool = False) -> BudgetDecision:
    limits = get_limits(tier)
    estimate = estimate_load_test_cost(concurrent_users, duration_seconds)

    if concurrent_users > limits["max_concurrent_users"]:
        return BudgetDecision(
            allowed=False,
            reason=f"Requested {concurrent_users} users exceeds {tier} tier max of {limits['max_concurrent_users']}",
            estimate=estimate
        )

    if duration_seconds > limits["max_test_duration_seconds"]:
        return BudgetDecision(
            allowed=False,
            reason=f"Requested duration {duration_seconds}s exceeds {tier} tier max of {limits['max_test_duration_seconds']}s",
            estimate=estimate
        )

    if concurrent_users > limits["requires_confirmation_above_users"] and not developer_confirmed:
        return BudgetDecision(
            allowed=False,
            reason="Requires explicit developer confirmation due to scale",
            requires_confirmation=True,
            estimate=estimate
        )

    return BudgetDecision(allowed=True, reason="within_limits", estimate=estimate)


def evaluate_chaos_test_plan(tier: str, developer_confirmed: bool = False) -> BudgetDecision:
    limits = get_limits(tier)
    if not limits["allow_chaos_engineering"]:
        return BudgetDecision(allowed=False, reason=f"{tier} tier does not permit chaos engineering")
    if not developer_confirmed:
        return BudgetDecision(allowed=False, reason="Chaos tests always require explicit confirmation", requires_confirmation=True)
    return BudgetDecision(allowed=True, reason="within_limits")


def evaluate_llm_usage(tier: str, planned_agent_calls: int, avg_tokens_per_call: int = 2000) -> BudgetDecision:
    limits = get_limits(tier)
    estimate = estimate_llm_cost(planned_agent_calls, avg_tokens_per_call)

    if estimate["estimated_total_tokens"] > limits["max_llm_tokens_per_run"]:
        return BudgetDecision(
            allowed=False,
            reason=f"Estimated {estimate['estimated_total_tokens']} tokens exceeds {tier} tier cap of {limits['max_llm_tokens_per_run']}",
            estimate=estimate
        )
    return BudgetDecision(allowed=True, reason="within_limits", estimate=estimate)
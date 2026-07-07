from Backend.core.core.policy_engine import PolicyEngine
from Backend.core.core.mock_dispatcher import mock_response
from Backend.core.core.audit_log import log_action

policy_engine = PolicyEngine()

def execute_action(agent_id: str, action: dict, sandbox_mode: bool = True, real_executor=None):
    """
    action = {type, target_domain, verified_domain, payload}
    real_executor = function to actually perform the action if allowed
    """
    decision = policy_engine.check(action, sandbox_mode)
    log_action(agent_id, action, decision)

    if decision == "allow":
        if real_executor:
            return real_executor(action)
        return {"status": "executed", "action": action["type"]}

    elif decision == "mock":
        return mock_response(action)

    else:  # block
        return {"status": "blocked", "action": action["type"]}
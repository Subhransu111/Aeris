import yaml

class PolicyEngine:
    def __init__(self, config_path="config/policy_rules.yaml"):
        with open(config_path) as f:
            self.rules = yaml.safe_load(f)["rules"]

    def check(self, action: dict, sandbox_mode: bool = True) -> str:
        """Returns: 'allow' | 'block' | 'mock'"""
        action_type = action["type"]
        target_domain = action.get("target_domain")
        verified_domain = action.get("verified_domain")

        # Hard rule: never touch outside verified target
        if target_domain and verified_domain and target_domain != verified_domain:
            return "block"

        rule = self.rules.get(action_type, "block")  # default deny

        if rule == "allow":
            return "allow"
        if rule == "block":
            return "mock" if action_type in ("payment_complete", "email_send", "sms_send") else "block"
        if rule == "allow_sandbox_only":
            return "allow" if sandbox_mode else "block"
        if rule == "block_always":
            return "block"

        return "block"
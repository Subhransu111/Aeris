# agents/provisioning/ensure_test_account.py
"""
Idempotent account setup: tries to register, falls back to login if the
account already exists. Works correctly whether the target DB is fresh
(disposable sandbox) or persistent (staging environment) - same config,
same code path, no branching needed based on which mode is in play.
"""
from agents.provisioning.config_driven_provisioning import provision_account_from_config


def ensure_test_account(page, registration_config: dict, base_domain: str, verified_domain: str) -> dict:
    result = provision_account_from_config(page, registration_config, base_domain, verified_domain)

    if result["status"] == "success":
        return {"status": "ready", "credentials": result["credentials"], "method": "registered"}

    if result["status"] == "failed" and result.get("reason") == "account_already_exists":
        # Account already exists in a persistent DB - that's fine, use the
        # same credentials the developer configured for login instead.
        return {
            "status": "ready",
            "credentials": {
                "username": registration_config["login_identifier_value"],
                "password": registration_config["login_password_value"],
            },
            "method": "already_existed",
        }

    return {"status": "failed", "reason": result.get("reason"), "log": result.get("log")}
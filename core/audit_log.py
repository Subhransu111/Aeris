import datetime
import json

LOG_FILE = "audit_log.jsonl"  # swap for Postgres later

def log_action(agent_id: str, action: dict, decision: str):
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "agent_id": agent_id,
        "action": action,
        "decision": decision
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
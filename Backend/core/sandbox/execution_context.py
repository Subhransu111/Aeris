from dataclasses import dataclass

@dataclass
class ExecutionContext:
    project_id: str
    org_id: str
    subscription_tier: str
    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    timeout_seconds: int = 600
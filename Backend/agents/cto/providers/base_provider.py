"""
Provider abstraction - CTO Agent never knows which model is behind it.
Swapping Gemini -> GPT-5 mini -> Claude is a one-line change at call site.
"""
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def generate_json(self, system_prompt: str, user_message: str, max_tokens: int = 3000) -> dict:
        """Returns {"status": "success", "data": dict} or {"status": "error", "reason": str}"""
        pass
"""
Gemini 2.5 Flash - large context, free tier quota, fast, structured JSON
output support. Good fit for report synthesis given budget constraints.
"""
import requests
import json
import os

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


class GeminiProvider:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    def generate_json(self, system_prompt: str, user_message: str, max_tokens: int = 6000) -> dict:
        if not self.api_key:
            return {"status": "error", "reason": "GEMINI_API_KEY not set"}

        payload = {
            "contents": [{"parts": [{"text": user_message}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }

        try:
            resp = requests.post(
                f"{GEMINI_API_URL}?key={self.api_key}",
                json=payload, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()

            candidate = data["candidates"][0]
            finish_reason = candidate.get("finishReason")
            text = candidate["content"]["parts"][0]["text"]

            if finish_reason == "MAX_TOKENS":
                return {"status": "error", "reason": "response_truncated_max_tokens", "raw": text[:1000]}

            parsed = json.loads(text)
            return {"status": "success", "data": parsed}

        except json.JSONDecodeError:
            return {"status": "error", "reason": "invalid_json_response", "raw": text[:1000] if 'text' in dir() else None}
        except Exception as e:
            return {"status": "error", "reason": str(e)[:300]}
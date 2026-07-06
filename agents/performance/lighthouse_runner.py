"""
Wraps the Lighthouse CLI to measure per-page performance. Zero custom
logic - Lighthouse already does TTFB/LCP/CPU/bundle-size measurement
correctly; we just invoke it and parse its JSON output.
"""
import subprocess
import json
import tempfile
import os


def run_lighthouse(url: str, timeout_seconds: int = 60) -> dict:
    output_path = os.path.join(tempfile.gettempdir(), f"lighthouse_{abs(hash(url))}.json")

    try:
        result = subprocess.run(
            [
                "lighthouse", url,
                "--output=json", f"--output-path={output_path}",
                "--chrome-flags=--headless --no-sandbox --disable-gpu",
                "--only-categories=performance",
                "--quiet",
            ],
            capture_output=True, text=True, timeout=timeout_seconds, shell=True
        )

        if not os.path.exists(output_path):
            return {"status": "failed", "detail": result.stderr[-500:] if result.stderr else "No output produced"}

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        os.remove(output_path)

        audits = data.get("audits", {})
        categories = data.get("categories", {})

        return {
            "status": "completed",
            "performance_score": round(categories.get("performance", {}).get("score", 0) * 100),
            "metrics": {
                "first_contentful_paint_ms": audits.get("first-contentful-paint", {}).get("numericValue"),
                "largest_contentful_paint_ms": audits.get("largest-contentful-paint", {}).get("numericValue"),
                "total_blocking_time_ms": audits.get("total-blocking-time", {}).get("numericValue"),
                "cumulative_layout_shift": audits.get("cumulative-layout-shift", {}).get("numericValue"),
                "speed_index_ms": audits.get("speed-index", {}).get("numericValue"),
                "time_to_interactive_ms": audits.get("interactive", {}).get("numericValue"),
            },
            "opportunities": [
                {"id": key, "title": audit.get("title"), "savings_ms": audit.get("numericValue")}
                for key, audit in audits.items()
                if audit.get("score") is not None and audit.get("score") < 0.9
                and audit.get("details", {}).get("type") == "opportunity"
            ][:5],
        }

    except subprocess.TimeoutExpired:
        return {"status": "timeout", "detail": f"Lighthouse exceeded {timeout_seconds}s"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:300]}
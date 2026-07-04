import os
import re

def get_screenshot_path(url: str, screenshot_dir: str = "screenshots") -> str:
    if not os.path.exists(screenshot_dir):
        os.makedirs(screenshot_dir)
    safe_filename = re.sub(r'[^a-zA-Z0-9]', '_', url.replace("https://", "").replace("http://", "")) + ".png"
    return os.path.join(screenshot_dir, safe_filename)

def cleanup_screenshots(screenshot_dir: str = "screenshots"):
    import shutil
    if os.path.exists(screenshot_dir):
        shutil.rmtree(screenshot_dir, ignore_errors=True)
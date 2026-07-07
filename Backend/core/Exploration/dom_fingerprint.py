import re
import hashlib

def compute_dom_fingerprint(html_content: str) -> str:
    html_content = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
    html_content = re.sub(r'\s(nonce|csrf|token|sessionid|id)="[^"]*"', '', html_content, flags=re.IGNORECASE)
    normalized = re.sub(r'\s+', ' ', html_content).strip().lower()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
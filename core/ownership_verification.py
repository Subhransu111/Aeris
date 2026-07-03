import dns.resolver
import secrets
import requests

import datetime

def generate_verification_token() -> str:
    return f"aegis-verify={secrets.token_hex(16)}"

## 1st way of verification: DNS TXT record
def check_dns_txt(domain: str , token:str) -> bool:
    try:
        answers = dns.resolver.resolve(domain, 'TXT')
        for rdata in answers:
            txt_value = rdata.to_text().strip('"')
            if txt_value == token:
                return True
        return False
    except Exception as e:
        print(f"DNS TXT record check failed for {domain}: {e}")
        return False

## 2nd way of verification: Github Repo 
def check_github_repo(repo_owner:str , repo_name:str , github_token:str) -> bool:
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    headers = {"Authorization": f"token {github_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return False
    data = resp.json()
    permissions = data.get("permissions", {})
    return permissions.get("admin", False) or permissions.get("push", False)


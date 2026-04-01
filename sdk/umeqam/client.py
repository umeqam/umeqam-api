import requests
from typing import Optional

BASE_URL = "https://umeqam-api-production.up.railway.app"

DOMAINS = ("medical", "legal", "finance", "mental")

class UMEQAMClient:
    def __init__(self, api_key: str, base_url: str = BASE_URL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        })

    def analyze(self, content: str, domain: str) -> dict:
        if domain not in DOMAINS:
            raise ValueError("domain must be one of: %s" % ", ".join(DOMAINS))
        url = "%s/v1/%s/analyze" % (self.base_url, domain)
        resp = self.session.post(url, json={"content": content}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def medical(self, content: str) -> dict:
        return self.analyze(content, "medical")

    def legal(self, content: str) -> dict:
        return self.analyze(content, "legal")

    def finance(self, content: str) -> dict:
        return self.analyze(content, "finance")

    def mental(self, content: str) -> dict:
        return self.analyze(content, "mental")

    def is_safe(self, content: str, domain: str) -> bool:
        result = self.analyze(content, domain)
        return result.get("overall_verdict") == "PASS"
"""
UMEQAM SDK — Main Client
"""
import json
from typing import Optional
from urllib import request, error
from urllib.parse import urljoin

from .models import HealthResult, AskResult
from .domains import MedicalAnalyzer, LegalAnalyzer, FinanceAnalyzer, MentalHealthAnalyzer
from .exceptions import AuthenticationError, RateLimitError, APIError, ConnectionError


DEFAULT_BASE_URL = "https://umeqam-api-production.up.railway.app"
DEFAULT_TIMEOUT  = 30


class UMEQAMClient:
    """
    UMEQAM API Client

    Usage:
        import umeqam

        client = umeqam.Client(api_key="umeqam-dev-key-001")

        # Check a medical AI response
        result = client.medical.analyze("Take aspirin daily without consulting a doctor.")
        print(result.verdict)        # FAIL
        print(result.compliance_score)  # 0.1
        print(result.flags)          # ['R-ME:OVERCONFIDENT', ...]

        # Check a financial AI response
        result = client.finance.analyze("Guaranteed 300% return on crypto.")
        if result.failed:
            print("Blocked:", result.recommendation)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        if not api_key:
            raise AuthenticationError("api_key is required")

        self.api_key  = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout

        # Domain analyzers
        self.medical = MedicalAnalyzer(self)
        self.legal   = LegalAnalyzer(self)
        self.finance = FinanceAnalyzer(self)
        self.mental  = MentalHealthAnalyzer(self)

    def _post(self, path: str, payload: dict) -> dict:
        url  = self.base_url + path
        body = json.dumps(payload).encode("utf-8")
        req  = request.Request(url, data=body, headers={"Content-Type": "application/json", "X-API-Key": self.api_key}, method="POST")
        return self._send(req)

    def _get(self, path: str) -> dict:
        url = self.base_url + path
        req = request.Request(url, headers={"X-API-Key": self.api_key}, method="GET")
        return self._send(req)

    def _send(self, req) -> dict:
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 403: raise AuthenticationError(f"Invalid API key (403): {body}")
            if e.code == 429: raise RateLimitError(f"Rate limit (429): {body}")
            raise APIError(f"HTTP {e.code}: {body}", status_code=e.code)
        except error.URLError as e:
            raise ConnectionError(f"Cannot reach UMEQAM API: {e.reason}")

    def health(self) -> HealthResult:
        data = self._get("/v1/health")
        return HealthResult(status=data.get("status"), version=data.get("version", ""), models=data.get("models", {}), layers=data.get("layers", {}), llm_ensemble=data.get("llm_ensemble", "unknown"), timestamp=data.get("timestamp", ""))

    def ask(self, question: str) -> AskResult:
        data = self._post("/v1/ask", {"question": question})
        return AskResult(request_id=data.get("request_id", ""), question=data.get("question", question), answers=data.get("answers", {}), risk_score=data.get("risk_score", 0.0), judge_results=data.get("judge_results", []), latency_ms=data.get("latency_ms", 0.0), timestamp=data.get("timestamp", ""))

    def analyze(self, content: str, domain: str, **kwargs):
        analyzers = {"medical": self.medical, "legal": self.legal, "finance": self.finance, "mental": self.mental}
        if domain not in analyzers:
            raise ValueError(f"Unknown domain: {domain!r}. Use: {list(analyzers)}")
        return analyzers[domain].analyze(content, **kwargs)

    def __repr__(self):
        return f"UMEQAMClient(base_url={self.base_url!r})"

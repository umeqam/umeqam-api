"""
UMEQAM SDK — Domain Analyzers
"""
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import UMEQAMClient

from .models import ComplianceResult, Judge


def _parse_result(data: dict) -> ComplianceResult:
    judges = [
        Judge(
            judge_id=j.get("judge_id", i),
            name=j.get("name", f"Judge_{i}"),
            verdict=j.get("verdict", "REVIEW"),
            confidence=j.get("confidence", 0.5),
            alarms=j.get("alarms", []),
        )
        for i, j in enumerate(data.get("judges", []))
    ]
    return ComplianceResult(
        request_id=data.get("request_id", ""),
        layer=data.get("layer", ""),
        overall_verdict=data.get("overall_verdict", "REVIEW"),
        compliance_score=data.get("compliance_score", 0.5),
        judges_passed=data.get("judges_passed", 0),
        judges_total=data.get("judges_total", 0),
        judges=judges,
        flags=data.get("flags", []),
        recommendation=data.get("recommendation", ""),
        timestamp=data.get("timestamp", ""),
        latency_ms=data.get("latency_ms", 0.0),
        engine=data.get("engine", "unknown"),
        llm_verdict=data.get("llm_verdict"),
        llm_confidence=data.get("llm_confidence"),
    )


class DomainAnalyzer:
    def __init__(self, client, domain: str, endpoint: str):
        self._client = client
        self._domain = domain
        self._endpoint = endpoint

    def analyze(self, content: str, context=None, jurisdiction="EU", strict_mode=True):
        payload = {"content": content, "jurisdiction": jurisdiction, "strict_mode": strict_mode}
        if context:
            payload["context"] = context
        data = self._client._post(self._endpoint, payload)
        return _parse_result(data)


class MedicalAnalyzer(DomainAnalyzer):
    def __init__(self, client):
        super().__init__(client, "medical", "/v1/medical/analyze")

class LegalAnalyzer(DomainAnalyzer):
    def __init__(self, client):
        super().__init__(client, "legal", "/v1/legal/analyze")

class FinanceAnalyzer(DomainAnalyzer):
    def __init__(self, client):
        super().__init__(client, "finance", "/v1/finance/analyze")

class MentalHealthAnalyzer(DomainAnalyzer):
    def __init__(self, client):
        super().__init__(client, "mental", "/v1/mental/analyze")

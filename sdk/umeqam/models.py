"""
UMEQAM SDK — Response Models
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Judge:
    judge_id: int
    name: str
    verdict: str
    confidence: float
    alarms: List[str] = field(default_factory=list)


@dataclass
class ComplianceResult:
    request_id: str
    layer: str
    overall_verdict: str
    compliance_score: float
    judges_passed: int
    judges_total: int
    judges: List[Judge]
    flags: List[str]
    recommendation: str
    timestamp: str
    latency_ms: float
    engine: str
    llm_verdict: Optional[str] = None
    llm_confidence: Optional[float] = None

    @property
    def passed(self) -> bool:
        return self.overall_verdict == "PASS"

    @property
    def failed(self) -> bool:
        return self.overall_verdict == "FAIL"

    @property
    def needs_review(self) -> bool:
        return self.overall_verdict == "REVIEW"

    def __repr__(self):
        return (f"ComplianceResult(verdict={self.overall_verdict!r}, "
                f"score={self.compliance_score}, latency={self.latency_ms}ms)")


@dataclass
class HealthResult:
    status: str
    version: str
    models: Dict[str, str]
    layers: Dict[str, str]
    llm_ensemble: str
    timestamp: str

    @property
    def operational(self) -> bool:
        return self.status == "operational"


@dataclass
class AskResult:
    request_id: str
    question: str
    answers: Dict[str, str]
    risk_score: float
    judge_results: List[dict]
    latency_ms: float
    timestamp: str

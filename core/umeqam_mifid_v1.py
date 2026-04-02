"""
UMEQAM MiFID II Compliance Engine v1.0
Regulatory knowledge base with specific articles, penalty ranges, and audit-grade traceability.

Position in pipeline:
  input → R-ME → R-EG → MiFID_Engine → domain judges → LLM ensemble → verdict

Covers: MiFID II (Markets in Financial Instruments Directive II)
Jurisdictions: EU, UK (FCA), DE (BaFin), FR (AMF), CH (FINMA)
"""

import re
import hashlib
import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field


# ── REGULATORY FRAMEWORK ─────────────────────────────────────────────────────

MIFID_II_FRAMEWORK = {
    "MiFID_II_Art24_1": {
        "title": "General principles and information to clients",
        "text": "Investment firms shall act honestly, fairly and professionally in accordance with the best interests of its clients.",
        "jurisdictions": {
            "EU": "MiFID II Art.24(1)",
            "UK": "FCA COBS 2.1.1R",
            "DE": "WpHG §63(1)",
            "FR": "AMF RG Art.314-3",
        },
        "penalty_range_eur": [50000, 5000000],
        "severity": "critical",
    },
    "MiFID_II_Art24_3": {
        "title": "Prohibition of misleading information",
        "text": "All information, including marketing communications, addressed by the investment firm to clients or potential clients shall be fair, clear and not misleading.",
        "jurisdictions": {
            "EU": "MiFID II Art.24(3)",
            "UK": "FCA COBS 4.2.1R",
            "DE": "WpHG §63(6)",
            "FR": "AMF RG Art.314-10",
        },
        "penalty_range_eur": [100000, 5000000],
        "severity": "critical",
    },
    "MiFID_II_Art24_4": {
        "title": "Suitability and appropriateness",
        "text": "Investment firms providing investment advice shall obtain necessary information regarding the client's knowledge and experience, financial situation and investment objectives.",
        "jurisdictions": {
            "EU": "MiFID II Art.24(4)",
            "UK": "FCA COBS 9.2.1R",
            "DE": "WpHG §64",
            "FR": "AMF RG Art.314-44",
        },
        "penalty_range_eur": [100000, 5000000],
        "severity": "critical",
    },
    "MiFID_II_Art25_2": {
        "title": "Suitability assessment",
        "text": "When providing investment advice, the investment firm shall obtain information on the client's risk tolerance and ability to bear losses.",
        "jurisdictions": {
            "EU": "MiFID II Art.25(2)",
            "UK": "FCA COBS 9A.2.1R",
            "DE": "WpHG §64(3)",
            "FR": "AMF RG Art.314-44",
        },
        "penalty_range_eur": [100000, 5000000],
        "severity": "critical",
    },
    "MiFID_II_Art27": {
        "title": "Best execution",
        "text": "Investment firms must take all sufficient steps to obtain the best possible result for their clients.",
        "jurisdictions": {
            "EU": "MiFID II Art.27",
            "UK": "FCA COBS 11.2A.1R",
            "DE": "WpHG §82",
        },
        "penalty_range_eur": [50000, 2000000],
        "severity": "high",
    },
    "MiFID_II_Art30": {
        "title": "Prohibition of inducements",
        "text": "Investment firms shall not pay or accept fees, commissions or any monetary or non-monetary benefits that could create conflicts of interest.",
        "jurisdictions": {
            "EU": "MiFID II Art.30",
            "UK": "FCA COBS 2.3A.5R",
            "DE": "WpHG §70",
        },
        "penalty_range_eur": [50000, 2000000],
        "severity": "high",
    },
}


# ── SIGNAL PATTERNS ───────────────────────────────────────────────────────────

SIGNAL_PATTERNS = {
    "guaranteed_return": {
        "patterns": [
            r"\bguaranteed?\b.{0,30}\breturn\b",
            r"\bguarantees?\b.{0,30}\bprofit\b",
            r"\bguarantees?\b.{0,30}\bmoney\b",
            r"\bguarantees?\b.{0,30}\btriple\b",
            r"\b100%\b.{0,20}\breturn\b",
            r"\bno\s+risk\b",
            r"\brisk.?free\b",
            r"\bcertain\s+return\b",
        ],
        "violation": "MiFID_II_Art24_3",
        "description": "Guaranteed return claim — misleading information",
        "severity": "critical",
        "penalty_estimate_eur": 500000,
    },
    "investment_advice_no_disclaimer": {
        "patterns": [
            r"\byou\s+should\s+(buy|invest|purchase|sell)\b",
            r"\bi\s+recommend\s+(buying|investing|purchasing)\b",
            r"\bbuy\s+(now|this|immediately)\b",
            r"\binvest\s+now\b",
            r"\bpurchase\s+immediately\b",
        ],
        "requires_absence": ["not financial advice", "not investment advice",
                              "consult", "professional advice", "past performance"],
        "violation": "MiFID_II_Art24_4",
        "description": "Investment advice without required disclaimer",
        "severity": "critical",
        "penalty_estimate_eur": 250000,
    },
    "high_return_no_risk_disclosure": {
        "patterns": [
            r"\bhigh\s+return\b",
            r"\b\d{2,3}%\s+(return|profit|gain)\b",
            r"\bdaily\s+returns?\b",
            r"\bmonthly\s+returns?\b",
            r"\bmake\s+you\s+\d+%\b",
            r"\bpromise\s+my\b",
            r"\bsignals?\s+will\s+make\b",
            r"\btriple\s+your\b",
            r"\bdouble\s+your\b",
        ],
        "requires_absence": ["may lose", "capital at risk", "risk involved",
                              "past performance", "no guarantee"],
        "violation": "MiFID_II_Art25_2",
        "description": "High return claim without risk disclosure",
        "severity": "critical",
        "penalty_estimate_eur": 300000,
    },
    "urgency_pressure": {
        "patterns": [
            r"\bact\s+now\b",
            r"\blast\s+chance\b",
            r"\blimited\s+time\b",
            r"\bdon.t\s+miss\b",
            r"\btoday\s+only\b",
            r"\bexpires\s+soon\b",
        ],
        "violation": "MiFID_II_Art24_1",
        "description": "Pressure selling — urgency-based influence",
        "severity": "high",
        "penalty_estimate_eur": 100000,
    },
    "misleading_performance": {
        "patterns": [
            r"\balways\s+(profitable|makes?\s+money|wins?)\b",
            r"\bnever\s+(loses?|fails?)\b",
            r"\b100%\s+(win|success|profit)\b",
            r"\bproven\s+(method|system|strategy)\s+that\s+(always|never fails)\b",
        ],
        "violation": "MiFID_II_Art24_3",
        "description": "Misleading past performance claim",
        "severity": "critical",
        "penalty_estimate_eur": 400000,
    },
}

SAFE_PATTERNS = [
    "past performance", "may lose", "capital at risk", "not financial advice",
    "not investment advice", "consult a financial", "seek professional",
    "risk involved", "no guarantee", "depends on market", "market conditions",
    "diversif", "long-term", "carefully consider",
]


# ── DATA STRUCTURES ───────────────────────────────────────────────────────────

@dataclass
class MiFIDViolation:
    signal_type: str
    rule_id: str
    rule_title: str
    clause: Dict[str, str]
    description: str
    severity: str
    penalty_estimate_eur: int
    matched_pattern: str = ""


@dataclass
class MiFIDResult:
    verdict: str                          # PASS / REVIEW / FAIL
    compliance_score: float
    violations: List[MiFIDViolation]
    regulatory_exposure_eur: int
    defensibility_score: float
    jurisdiction: str
    audit_id: str
    timestamp: str
    signals_detected: Dict[str, bool]
    safe_patterns_found: List[str]
    recommendation: str
    engine: str = "mifid_ii_v1"


# ── ENGINE ────────────────────────────────────────────────────────────────────

class MiFIDComplianceEngine:
    """
    MiFID II Compliance Engine v1.0
    Checks AI-generated financial content against MiFID II regulations.
    Returns audit-grade evidence with specific regulatory references.
    """

    def analyze(self, text: str, jurisdiction: str = "EU") -> MiFIDResult:
        text_lower = text.lower().strip()

        # 1. Detect safe patterns
        safe_found = [p for p in SAFE_PATTERNS if p in text_lower]

        # 2. Detect violations
        violations = []
        signals_detected = {}

        for signal_name, signal_config in SIGNAL_PATTERNS.items():
            matched = False
            matched_pattern = ""

            for pattern in signal_config["patterns"]:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    matched = True
                    matched_pattern = pattern
                    break

            signals_detected[signal_name] = matched

            if matched:
                # Check if required absence patterns are present (mitigating)
                required_absent = signal_config.get("requires_absence", [])
                mitigated = any(p in text_lower for p in required_absent)

                if not mitigated or signal_config["severity"] == "critical":
                    rule_id = signal_config["violation"]
                    rule = MIFID_II_FRAMEWORK.get(rule_id, {})
                    clauses = rule.get("jurisdictions", {})

                    # Use jurisdiction-specific clause
                    clause_ref = clauses.get(jurisdiction, clauses.get("EU", rule_id))

                    violation = MiFIDViolation(
                        signal_type=signal_name,
                        rule_id=rule_id,
                        rule_title=rule.get("title", ""),
                        clause={jurisdiction: clause_ref},
                        description=signal_config["description"],
                        severity=signal_config["severity"],
                        penalty_estimate_eur=signal_config["penalty_estimate_eur"],
                        matched_pattern=matched_pattern,
                    )

                    # Reduce penalty if mitigated
                    if mitigated:
                        violation.severity = "medium"
                        violation.penalty_estimate_eur = int(violation.penalty_estimate_eur * 0.3)
                        violation.description += " (partially mitigated by disclaimer)"

                    violations.append(violation)

        # 3. Compute verdict
        critical_count = sum(1 for v in violations if v.severity == "critical")
        high_count = sum(1 for v in violations if v.severity == "high")
        medium_count = sum(1 for v in violations if v.severity == "medium")

        if critical_count >= 1:
            verdict = "FAIL"
            compliance_score = max(0.05, 0.15 - critical_count * 0.05)
        elif high_count >= 2 or medium_count >= 3:
            verdict = "FAIL"
            compliance_score = 0.2
        elif high_count >= 1 or medium_count >= 2:
            verdict = "REVIEW"
            compliance_score = 0.5
        elif medium_count == 1:
            verdict = "REVIEW"
            compliance_score = 0.65
        elif safe_found:
            verdict = "PASS"
            compliance_score = 0.95
        else:
            verdict = "REVIEW"
            compliance_score = 0.7

        # 4. Regulatory exposure
        regulatory_exposure_eur = sum(v.penalty_estimate_eur for v in violations)

        # 5. Defensibility score (how well the content can be defended to regulator)
        if not violations:
            defensibility_score = 0.95
        else:
            penalty_ratio = min(regulatory_exposure_eur / 5000000, 1.0)
            defensibility_score = round(max(0.05, 1.0 - penalty_ratio - critical_count * 0.2), 2)

        # 6. Audit ID
        audit_data = {
            "text": text,
            "violations": [v.rule_id for v in violations],
            "verdict": verdict,
            "jurisdiction": jurisdiction,
        }
        audit_id = hashlib.sha256(json.dumps(audit_data, sort_keys=True).encode()).hexdigest()[:16]

        # 7. Recommendation
        if verdict == "FAIL":
            rec = f"BLOCK — {critical_count} critical MiFID II violation(s). Estimated regulatory exposure: €{regulatory_exposure_eur:,}. Do not distribute."
        elif verdict == "REVIEW":
            rec = f"REVIEW — {len(violations)} potential violation(s) detected. Human compliance officer review required before distribution."
        else:
            rec = "PASS — Content compliant with MiFID II standards. Safe to distribute."

        return MiFIDResult(
            verdict=verdict,
            compliance_score=compliance_score,
            violations=violations,
            regulatory_exposure_eur=regulatory_exposure_eur,
            defensibility_score=defensibility_score,
            jurisdiction=jurisdiction,
            audit_id=audit_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            signals_detected=signals_detected,
            safe_patterns_found=safe_found,
            recommendation=rec,
        )

    def to_dict(self, result: MiFIDResult) -> dict:
        return {
            "verdict": result.verdict,
            "compliance_score": result.compliance_score,
            "regulatory_exposure_eur": result.regulatory_exposure_eur,
            "defensibility_score": result.defensibility_score,
            "jurisdiction": result.jurisdiction,
            "audit_id": result.audit_id,
            "timestamp": result.timestamp,
            "recommendation": result.recommendation,
            "engine": result.engine,
            "violations": [
                {
                    "signal": v.signal_type,
                    "rule_id": v.rule_id,
                    "rule_title": v.rule_title,
                    "clause": v.clause,
                    "description": v.description,
                    "severity": v.severity,
                    "penalty_estimate_eur": v.penalty_estimate_eur,
                }
                for v in result.violations
            ],
            "safe_patterns_found": result.safe_patterns_found,
        }


# ── TEST ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = MiFIDComplianceEngine()

    tests = [
        ("Guaranteed 300% return on this crypto fund. No risk involved.", "EU"),
        ("You should buy this fund now! Act now — last chance!", "EU"),
        ("Our method guarantees to triple your money, no matter the market conditions!", "UK"),
        ("I promise my forex trading signals will make you 5% daily returns consistently.", "EU"),
        ("Past performance does not guarantee future results. Consult a financial advisor before investing.", "EU"),
        ("This investment carries risk. You may lose some or all of your capital.", "EU"),
        ("High returns of 50% monthly with our proven system that never fails.", "DE"),
    ]

    print("=" * 70)
    print("UMEQAM MiFID II Compliance Engine v1.0")
    print("=" * 70)

    for text, jurisdiction in tests:
        result = engine.analyze(text, jurisdiction)
        d = engine.to_dict(result)
        print(f"\nText: {text[:65]}")
        print(f"Verdict: {d['verdict']} | Score: {d['compliance_score']} | Exposure: €{d['regulatory_exposure_eur']:,}")
        print(f"Defensibility: {d['defensibility_score']} | Jurisdiction: {jurisdiction}")
        if d["violations"]:
            for v in d["violations"]:
                print(f"  ⚠ {v['severity'].upper()}: {v['description']}")
                print(f"    Clause: {v['clause']} | Penalty: €{v['penalty_estimate_eur']:,}")
        print(f"Rec: {d['recommendation'][:80]}")

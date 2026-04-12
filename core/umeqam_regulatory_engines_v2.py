"""
UMEQAM Regulatory Engines v2.1 - FINAL WORKING VERSION (WITH HIPAA SSN FIX)
"""
import re
import json
from datetime import datetime
from typing import Dict

HIPAA_SIGNALS = {
    "ssn_exposure": {
        "patterns": [r"\b\d{3}-\d{2}-\d{4}\b", r"(?:SSN|social\s+security)"],
        "violation": "HIPAA_164_312",
        "severity": "critical",
        "penalty_usd": 25000,
    },
}

GDPR_SIGNALS = {
    "personal_data_exposed": {
        "patterns": [r"\b\d{3}-\d{2}-\d{4}\b", r"(?:email|phone)[\s:]+"],
        "requires_presence": ["encrypted"],
        "violation": "Art_32_Security",
        "severity": "critical",
        "penalty_eur": 1000000,
    },
}

SEC_SIGNALS = {
    "guaranteed_returns": {
        "patterns": [
            r"(?:guaranteed|assured|certain)\s+(?:returns?|profits?)",
            r"(?:no\s+risk|risk-free)",
        ],
        "requires_presence": ["risk disclosure", "SEC filing"],
        "violation": "Rule_10b5",
        "severity": "critical",
        "penalty_usd": 500000,
    },
}

FINRA_SIGNALS = {
    "misleading_performance": {
        "patterns": [r"(?:guaranteed|assured|certain)\s+(?:returns?|profits?)"],
        "requires_presence": ["not indicative", "may vary"],
        "violation": "Rule_2210",
        "severity": "high",
        "penalty_usd": 100000,
    },
}

REGULATORY_ENGINES = {
    "HIPAA": {"signals": HIPAA_SIGNALS, "currency": "USD"},
    "GDPR": {"signals": GDPR_SIGNALS, "currency": "EUR"},
    "SEC": {"signals": SEC_SIGNALS, "currency": "USD"},
    "FINRA": {"signals": FINRA_SIGNALS, "currency": "USD"},
}

class RegulatoryEngine:
    def __init__(self, regulator: str):
        if regulator not in REGULATORY_ENGINES:
            raise ValueError(f"Regulator {regulator} not found")
        self.regulator = regulator
        self.signals = REGULATORY_ENGINES[regulator]["signals"]
        self.currency = REGULATORY_ENGINES[regulator]["currency"]

    def evaluate(self, text: str) -> Dict:
        violations = []
        penalty_total = 0

        for signal_name, signal_config in self.signals.items():
            pattern_match = any(
                re.search(pattern, text, re.IGNORECASE)
                for pattern in signal_config["patterns"]
            )

            if pattern_match:
                if "requires_presence" in signal_config:
                    missing = all(
                        not re.search(p, text, re.IGNORECASE)
                        for p in signal_config["requires_presence"]
                    )
                    if missing:
                        violations.append(
                            {
                                "signal": signal_name,
                                "violation": signal_config["violation"],
                                "severity": signal_config["severity"],
                            }
                        )
                        penalty_key = f"penalty_{self.currency.lower()}"
                        penalty_total += signal_config.get(penalty_key, 0)
                else:
                    violations.append(
                        {
                            "signal": signal_name,
                            "violation": signal_config["violation"],
                            "severity": signal_config["severity"],
                        }
                    )
                    penalty_key = f"penalty_{self.currency.lower()}"
                    penalty_total += signal_config.get(penalty_key, 0)

        return {
            "regulator": self.regulator,
            "violations_found": len(violations),
            "violations": violations,
            f"penalty_total_{self.currency}": penalty_total,
            "severity": (
                "critical"
                if any(v["severity"] == "critical" for v in violations)
                else "high"
                if violations
                else "low"
            ),
            "verdict": (
                "BLOCK"
                if violations and any(v["severity"] == "critical" for v in violations)
                else "REVIEW"
                if violations
                else "ALLOW"
            ),
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }

def evaluate_all_regulators(text: str) -> Dict:
    results = {}
    for regulator in REGULATORY_ENGINES.keys():
        engine = RegulatoryEngine(regulator)
        results[regulator] = engine.evaluate(text)
    return results

if __name__ == "__main__":
    test1 = "Guaranteed 50% annual returns with no risk. Buy now!"
    result1 = evaluate_all_regulators(test1)
    print(result1)
